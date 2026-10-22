package lab.enterprise.missions.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigInteger;
import org.junit.jupiter.api.Test;

class MissionIdsTest {
    @Test void encodesBase36UppercaseZeroPaddedToNineCharacters() {
        assertEquals("ST-000000001", MissionIds.fromSequence(1));
        assertEquals("ST-00000000A", MissionIds.fromSequence(10));
        assertEquals("ST-000000010", MissionIds.fromSequence(36));
        // A seeded release identifier is the same encoding of its ordinal.
        assertEquals("ST-00000LD4O", MissionIds.fromSequence(Long.parseLong("LD4O", 36)));
    }

    @Test void theLargestSequenceValueFillsTheSuffix() {
        assertEquals("ST-ZZZZZZZZZ", MissionIds.fromSequence(MissionIds.MAX));
        assertEquals(BigInteger.valueOf(36).pow(9).subtract(BigInteger.ONE), BigInteger.valueOf(MissionIds.MAX));
    }

    @Test void overflowAndNonPositiveValuesFailInsteadOfWrapping() {
        assertThrows(IllegalStateException.class, () -> MissionIds.fromSequence(MissionIds.MAX + 1));
        assertThrows(IllegalStateException.class, () -> MissionIds.fromSequence(0));
        assertThrows(IllegalStateException.class, () -> MissionIds.fromSequence(-5));
    }
}
