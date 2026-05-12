package dev.anip.core;

public record InputMeaning(
        String label,
        String value,
        String description
) {
    public InputMeaning {
        if (description == null) description = "";
    }
}
