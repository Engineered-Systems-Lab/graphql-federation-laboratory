package lab.enterprise.missions.domain;

import java.util.Locale;

/** Mission identifiers: a base-36 payload of the Oracle sequence, zero-padded to the nine-character suffix. */
public final class MissionIds {
    /** 36^9 - 1, the largest payload the nine-character suffix holds. */
    public static final long MAX = 101_559_956_668_415L;

    private MissionIds() { }

    public static String fromSequence(long value) {
        if (value < 1 || value > MAX) throw new IllegalStateException("Mission identifier sequence out of range");
        String payload = Long.toString(value, 36).toUpperCase(Locale.ROOT);
        return "ST-" + "0".repeat(9 - payload.length()) + payload;
    }
}
