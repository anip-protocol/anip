use std::{
    env,
    fs::{self, OpenOptions},
    io::Write,
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Mutex, OnceLock},
    time::Duration,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;
use tauri::{path::BaseDirectory, plugin::Builder as PluginBuilder, Manager, Runtime, Webview};

static GTM_RUNTIME_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();
static GTM_RUNTIME_PORT: OnceLock<u16> = OnceLock::new();
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const ALLOWED_EXTERNAL_URL_PREFIXES: &[&str] = &[
    "https://anip.dev/",
    "https://registry.anip.dev/",
    "https://github.com/anip-protocol/anip/",
];

fn configured_runtime_port() -> Option<u16> {
    env::var("GTM_DESKTOP_API_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
}

fn allocate_runtime_port() -> u16 {
    if let Some(port) = configured_runtime_port() {
        return port;
    }

    TcpListener::bind(SocketAddr::from(([127, 0, 0, 1], 0)))
        .ok()
        .and_then(|listener| listener.local_addr().ok())
        .map(|addr| addr.port())
        .unwrap_or(9310)
}

fn runtime_port() -> u16 {
    *GTM_RUNTIME_PORT.get_or_init(allocate_runtime_port)
}

fn runtime_base_url() -> String {
    format!("http://127.0.0.1:{}", runtime_port())
}

fn is_loopback_runtime_url(url: &str) -> bool {
    url.starts_with("http://127.0.0.1:") || url.starts_with("http://localhost:")
}

fn is_allowed_external_url(url: &str) -> bool {
    ALLOWED_EXTERNAL_URL_PREFIXES
        .iter()
        .any(|prefix| url == prefix.trim_end_matches('/') || url.starts_with(prefix))
}

fn open_external_url_impl(url: &str) -> Result<(), String> {
    if !is_allowed_external_url(url) {
        return Err("external URL is not allowed".to_string());
    }

    #[cfg(target_os = "macos")]
    let status = Command::new("open").arg(url).status();

    #[cfg(target_os = "windows")]
    let status = Command::new("cmd").args(["/C", "start", "", url]).status();

    #[cfg(all(unix, not(target_os = "macos")))]
    let status = Command::new("xdg-open").arg(url).status();

    status
        .map_err(|err| format!("failed to open external URL: {err}"))
        .and_then(|status| {
            if status.success() {
                Ok(())
            } else {
                Err(format!("failed to open external URL: status {status}"))
            }
        })
}

fn external_link_navigation_plugin<R: Runtime>() -> tauri::plugin::TauriPlugin<R> {
    PluginBuilder::new("gtm-external-links")
        .js_init_script(
            r#"
            document.addEventListener('click', function (event) {
              var target = event.target;
              var anchor = target && target.closest ? target.closest('a[href]') : null;
              if (!anchor) return;
              var href = anchor.href || '';
              if (!href || href.startsWith('http://127.0.0.1:') || href.startsWith('http://localhost:')) return;
              if (!href.startsWith('http://') && !href.startsWith('https://')) return;
              event.preventDefault();
              window.location.href = href;
            }, true);
            "#,
        )
        .on_navigation(|_webview: &Webview<R>, url| {
            let value = url.as_str();
            if is_loopback_runtime_url(value) || value.starts_with("tauri://") {
                return true;
            }
            if is_allowed_external_url(value) {
                let _ = open_external_url_impl(value);
                return false;
            }
            false
        })
        .build()
}

fn runtime_is_running() -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], runtime_port()));
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

fn configured_runtime_launcher() -> Option<PathBuf> {
    env::var_os("ANIP_GTM_RUNTIME_LAUNCHER")
        .map(PathBuf::from)
        .filter(|path| path.exists())
}

fn desktop_log_path() -> Option<PathBuf> {
    #[cfg(windows)]
    {
        let base = env::var_os("LOCALAPPDATA")
            .or_else(|| env::var_os("APPDATA"))
            .map(PathBuf::from)?;
        return Some(
            base.join("ANIP")
                .join("GTM Agent Desktop")
                .join("desktop-runtime.log"),
        );
    }

    #[cfg(not(windows))]
    {
        let home = env::var_os("HOME").map(PathBuf::from)?;
        Some(
            home.join("Library")
                .join("Logs")
                .join("GTM Agent Desktop")
                .join("desktop-runtime.log"),
        )
    }
}

fn append_desktop_log(message: &str) {
    let Some(path) = desktop_log_path() else {
        return;
    };
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{message}");
    }
}

fn stop_runtime_sidecar() {
    let Some(child_slot) = GTM_RUNTIME_CHILD.get() else {
        return;
    };
    let Ok(mut guard) = child_slot.lock() else {
        return;
    };
    let Some(mut child) = guard.take() else {
        return;
    };

    append_desktop_log("Stopping GTM Agent runtime sidecar process");
    let _ = child.kill();
    let _ = child.wait();
}

fn target_triple() -> &'static str {
    if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        "aarch64-apple-darwin"
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        "x86_64-apple-darwin"
    } else if cfg!(all(target_os = "windows", target_arch = "x86_64")) {
        "x86_64-pc-windows-msvc.exe"
    } else if cfg!(all(target_os = "linux", target_arch = "x86_64")) {
        "x86_64-unknown-linux-gnu"
    } else {
        ""
    }
}

fn bundled_runtime_launcher(app: &tauri::App) -> Option<PathBuf> {
    let triple = target_triple();
    if triple.is_empty() {
        return None;
    }
    app.path()
        .resolve(
            format!("bin/gtm-agent-desktop-runtime-{triple}"),
            BaseDirectory::Resource,
        )
        .ok()
        .filter(|path| path.exists())
}

fn macos_bundle_runtime_launcher() -> Option<PathBuf> {
    let triple = target_triple();
    if triple.is_empty() {
        return None;
    }
    let executable = env::current_exe().ok()?;
    let contents_dir = executable.parent()?.parent()?;
    let candidate = contents_dir
        .join("Resources")
        .join("bin")
        .join(format!("gtm-agent-desktop-runtime-{triple}"));
    candidate.exists().then_some(candidate)
}

#[cfg(debug_assertions)]
fn development_runtime_launcher() -> Option<PathBuf> {
    let script =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../scripts/start-desktop-runtime.sh");
    script.exists().then_some(script)
}

#[cfg(not(debug_assertions))]
fn development_runtime_launcher() -> Option<PathBuf> {
    None
}

fn start_runtime_if_configured(app: &tauri::App) {
    if env::var("ANIP_GTM_SKIP_RUNTIME_LAUNCH").ok().as_deref() == Some("1") {
        append_desktop_log("GTM runtime launch skipped by ANIP_GTM_SKIP_RUNTIME_LAUNCH=1");
        return;
    }
    if runtime_is_running() {
        append_desktop_log(&format!(
            "GTM runtime already running on {}",
            runtime_base_url()
        ));
        return;
    }

    let Some(launcher) = configured_runtime_launcher()
        .or_else(|| bundled_runtime_launcher(app))
        .or_else(macos_bundle_runtime_launcher)
        .or_else(development_runtime_launcher)
    else {
        append_desktop_log("No GTM runtime launcher found");
        return;
    };

    append_desktop_log(&format!(
        "Launching GTM runtime on {}: {}",
        runtime_base_url(),
        launcher.display()
    ));
    let log_file = desktop_log_path().and_then(|path| {
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        OpenOptions::new().create(true).append(true).open(path).ok()
    });
    let stdout = log_file
        .as_ref()
        .and_then(|file| file.try_clone().ok())
        .map(Stdio::from)
        .unwrap_or_else(Stdio::null);
    let stderr = log_file.map(Stdio::from).unwrap_or_else(Stdio::null);

    let mut command = Command::new(&launcher);
    command
        .env("GTM_DESKTOP_API_PORT", runtime_port().to_string())
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr);

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let Ok(child) = command.spawn() else {
        append_desktop_log(&format!(
            "Failed to spawn GTM runtime sidecar: {}",
            launcher.display()
        ));
        return;
    };

    append_desktop_log("GTM runtime sidecar process spawned");

    let child_slot = GTM_RUNTIME_CHILD.get_or_init(|| Mutex::new(None));
    if let Ok(mut guard) = child_slot.lock() {
        *guard = Some(child);
    }
}

#[tauri::command]
fn gtm_agent_base_url() -> String {
    runtime_base_url()
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    open_external_url_impl(&url)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(external_link_navigation_plugin())
        .invoke_handler(tauri::generate_handler![
            gtm_agent_base_url,
            open_external_url
        ])
        .setup(|app| {
            start_runtime_if_configured(app);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running GTM Agent Desktop");

    app.run(|_app_handle, event| {
        if matches!(
            event,
            tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
        ) {
            stop_runtime_sidecar();
        }
    });
}
