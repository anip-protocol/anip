package dev.anip.service;

import java.time.Instant;
import java.util.*;

public class AuditAggregator {
    private final long windowSeconds;
    private final Map<WindowKey, Bucket> windows = new LinkedHashMap<>();

    public AuditAggregator(int windowSeconds) {
        this.windowSeconds = windowSeconds;
    }

    public synchronized void submit(Map<String, Object> event) {
        String actorKey = strOr(event, "actor_key", "anonymous");
        String capability = strOr(event, "capability", "_pre_auth");
        String failureType = strOr(event, "failure_type", "unknown");
        Instant ts = parseTimestamp(event);
        long epoch = ts.getEpochSecond() - (ts.getEpochSecond() % windowSeconds);
        var wk = new WindowKey(actorKey, capability, failureType, epoch);
        var bucket = windows.computeIfAbsent(wk, k -> {
            String detail = (String) event.get("detail");
            if (detail != null && detail.length() > 200) detail = detail.substring(0, 200);
            return new Bucket(ts, detail);
        });
        bucket.events.add(event);
        if (ts.isAfter(bucket.lastSeen)) bucket.lastSeen = ts;
    }

    public synchronized List<Object> flush(Instant now) {
        List<Object> results = new ArrayList<>();
        long nowEpoch = now.getEpochSecond();
        var it = windows.entrySet().iterator();
        while (it.hasNext()) {
            var e = it.next();
            var wk = e.getKey();
            var bucket = e.getValue();
            long windowEnd = wk.epoch + windowSeconds;
            if (windowEnd > nowEpoch) continue;
            String windowStart = Instant.ofEpochSecond(wk.epoch).toString();
            String windowEndStr = Instant.ofEpochSecond(windowEnd).toString();
            if (bucket.events.size() == 1) {
                results.add(bucket.events.get(0));
            } else {
                Map<String, Object> aggregated = new LinkedHashMap<>();
                aggregated.put("entry_type", "aggregated");
                aggregated.put("event_class", "repeated_low_value_denial");
                aggregated.put("retention_tier", "aggregate_only");
                aggregated.put("grouping_key", Map.of(
                    "actor_key", wk.actorKey, "capability", wk.capability, "failure_type", wk.failureType));
                aggregated.put("aggregation_window", Map.of("start", windowStart, "end", windowEndStr));
                aggregated.put("aggregation_count", bucket.events.size());
                aggregated.put("count", bucket.events.size());
                aggregated.put("first_seen", bucket.firstSeen.toString());
                aggregated.put("last_seen", bucket.lastSeen.toString());
                aggregated.put("representative_detail", bucket.representativeDetail);
                aggregated.put("capability", wk.capability);
                aggregated.put("failure_type", wk.failureType);
                aggregated.put("success", false);
                results.add(aggregated);
            }
            it.remove();
        }
        return results;
    }

    private static String strOr(Map<String, Object> m, String key, String def) {
        Object v = m.get(key);
        return v instanceof String s && !s.isEmpty() ? s : def;
    }

    private static Instant parseTimestamp(Map<String, Object> event) {
        Object ts = event.get("timestamp");
        if (ts instanceof String s) {
            try { return Instant.parse(s); } catch (Exception ignored) {}
        }
        return Instant.now();
    }

    private record WindowKey(String actorKey, String capability, String failureType, long epoch) {}

    private static class Bucket {
        final List<Map<String, Object>> events = new ArrayList<>();
        final Instant firstSeen;
        Instant lastSeen;
        final String representativeDetail;
        Bucket(Instant firstSeen, String detail) {
            this.firstSeen = firstSeen;
            this.lastSeen = firstSeen;
            this.representativeDetail = detail;
        }
    }
}
