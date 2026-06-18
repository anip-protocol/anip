package registryapi

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

const (
	registryOAuthStateCookieName = "anip_registry_oauth_state"
	registrySessionCookieName    = "anip_registry_session"
	registrySessionTokenPrefix   = "anip_sid_"
)

type GitHubOAuthExchangeFunc func(ctx context.Context, code string) (GitHubOAuthIdentity, error)

func defaultGitHubOAuthExchange(clientID string, clientSecret string, redirectURI string) GitHubOAuthExchangeFunc {
	return func(ctx context.Context, code string) (GitHubOAuthIdentity, error) {
		if strings.TrimSpace(clientID) == "" || strings.TrimSpace(clientSecret) == "" {
			return GitHubOAuthIdentity{}, errors.New("github oauth client id and secret are required")
		}
		form := url.Values{}
		form.Set("client_id", clientID)
		form.Set("client_secret", clientSecret)
		form.Set("code", code)
		if strings.TrimSpace(redirectURI) != "" {
			form.Set("redirect_uri", redirectURI)
		}
		request, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://github.com/login/oauth/access_token", bytes.NewBufferString(form.Encode()))
		if err != nil {
			return GitHubOAuthIdentity{}, err
		}
		request.Header.Set("Accept", "application/json")
		request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		response, err := http.DefaultClient.Do(request)
		if err != nil {
			return GitHubOAuthIdentity{}, err
		}
		defer response.Body.Close()
		var tokenPayload struct {
			AccessToken string `json:"access_token"`
			Error       string `json:"error"`
			Description string `json:"error_description"`
		}
		if err := json.NewDecoder(response.Body).Decode(&tokenPayload); err != nil {
			return GitHubOAuthIdentity{}, err
		}
		if response.StatusCode < 200 || response.StatusCode >= 300 || tokenPayload.AccessToken == "" {
			if tokenPayload.Description != "" {
				return GitHubOAuthIdentity{}, fmt.Errorf("github oauth exchange failed: %s", tokenPayload.Description)
			}
			return GitHubOAuthIdentity{}, fmt.Errorf("github oauth exchange failed: %s", response.Status)
		}

		profileRequest, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://api.github.com/user", nil)
		if err != nil {
			return GitHubOAuthIdentity{}, err
		}
		profileRequest.Header.Set("Authorization", "Bearer "+tokenPayload.AccessToken)
		profileRequest.Header.Set("Accept", "application/vnd.github+json")
		profileResponse, err := http.DefaultClient.Do(profileRequest)
		if err != nil {
			return GitHubOAuthIdentity{}, err
		}
		defer profileResponse.Body.Close()
		if profileResponse.StatusCode < 200 || profileResponse.StatusCode >= 300 {
			return GitHubOAuthIdentity{}, fmt.Errorf("github profile request failed: %s", profileResponse.Status)
		}
		var profile struct {
			ID        int64  `json:"id"`
			Login     string `json:"login"`
			Name      string `json:"name"`
			Email     string `json:"email"`
			AvatarURL string `json:"avatar_url"`
			HTMLURL   string `json:"html_url"`
		}
		if err := json.NewDecoder(profileResponse.Body).Decode(&profile); err != nil {
			return GitHubOAuthIdentity{}, err
		}
		displayName := strings.TrimSpace(profile.Name)
		if displayName == "" {
			displayName = profile.Login
		}
		return GitHubOAuthIdentity{
			GitHubUserID: fmt.Sprintf("%d", profile.ID),
			Login:        profile.Login,
			DisplayName:  displayName,
			Email:        profile.Email,
			AvatarURL:    profile.AvatarURL,
			ProfileURL:   profile.HTMLURL,
		}, nil
	}
}

func browserSessionCookie(token string, secure bool, maxAge int) *http.Cookie {
	return &http.Cookie{
		Name:     registrySessionCookieName,
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   secure,
		MaxAge:   maxAge,
	}
}

func oauthStateCookie(state string, secure bool) *http.Cookie {
	return &http.Cookie{
		Name:     registryOAuthStateCookieName,
		Value:    state,
		Path:     "/registry-api/v1/auth/github",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   secure,
		MaxAge:   int((10 * time.Minute).Seconds()),
	}
}

func expiredCookie(name string, path string, secure bool) *http.Cookie {
	return &http.Cookie{
		Name:     name,
		Value:    "",
		Path:     path,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   secure,
		MaxAge:   -1,
	}
}

func registrySessionSecretHash(secret string) string {
	sum := sha256.Sum256([]byte(secret))
	return hex.EncodeToString(sum[:])
}

func parseRegistrySessionToken(token string) (string, string, bool) {
	token = strings.TrimSpace(token)
	if !strings.HasPrefix(token, registrySessionTokenPrefix) {
		return "", "", false
	}
	remainder := strings.TrimPrefix(token, registrySessionTokenPrefix)
	sessionID, secret, ok := strings.Cut(remainder, "_")
	if !ok || strings.TrimSpace(sessionID) == "" || strings.TrimSpace(secret) == "" {
		return "", "", false
	}
	return sessionID, secret, true
}

func sanitizePublisherIDFromGitHubLogin(login string, fallbackSubject string) string {
	login = strings.ToLower(strings.TrimSpace(login))
	clean := regexp.MustCompile(`[^a-z0-9-]+`).ReplaceAllString(login, "-")
	clean = strings.Trim(clean, "-")
	if clean != "" {
		return clean
	}
	return "github-" + strings.TrimSpace(fallbackSubject)
}
