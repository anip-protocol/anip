package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

public record InputMeaning(
        @JsonProperty("label") String label,
        @JsonProperty("value") String value,
        @JsonProperty("description") String description
) {
    @JsonCreator
    public InputMeaning {
        if (description == null) description = "";
    }
}
