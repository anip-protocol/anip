package {{ANIP_JAVA_PACKAGE_NAME}};

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SupersetDiscoveryEndpointsTest {

    private static List<String> kinds(String assetType) {
        return SupersetBackendAdapter.discoveryEndpoints(assetType).stream().map(endpoint -> endpoint[0]).toList();
    }

    // "all" is asset_type's declared default, so it is what a call without
    // asset_type carries; it must not filter out every endpoint.
    @Test
    void allAndAnEmptyAssetTypeReadEveryCatalog() {
        assertEquals(List.of("dataset", "chart", "dashboard"), kinds("all"));
        assertEquals(List.of("dataset", "chart", "dashboard"), kinds(""));
    }

    @Test
    void aNamedKindReadsItsCatalog() {
        assertEquals(List.of("chart"), kinds("chart"));
        // metric and dimension are declared values without a Superset list endpoint.
        assertEquals(List.of(), kinds("metric"));
    }
}
