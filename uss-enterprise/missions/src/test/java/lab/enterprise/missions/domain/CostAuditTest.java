package lab.enterprise.missions.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class CostAuditTest {
    private static BigDecimal d(String value) { return new BigDecimal(value); }

    @Test void absentToAbsentOmitsBoth() {
        var audit = CostAudit.of(null, null);
        assertNull(audit.resulting());
        assertNull(audit.change());
    }

    @Test void absentToValueRecordsOnlyTheValue() {
        var audit = CostAudit.of(null, d("0.00"));
        assertEquals(d("0.00"), audit.resulting());
        assertNull(audit.change());
    }

    @Test void valueToSameValueRecordsZero() {
        var audit = CostAudit.of(d("140000"), d("140000.00"));
        assertEquals("0.00", audit.change().toPlainString());
    }

    @Test void increaseIsPositiveWithoutPlusAndDecreaseIsNegative() {
        assertEquals("15000.00", CostAudit.of(d("125000.00"), d("140000.00")).change().toPlainString());
        assertEquals("-15000.00", CostAudit.of(d("140000.00"), d("125000.00")).change().toPlainString());
        assertEquals("-0.01", CostAudit.of(d("5.01"), d("5.00")).change().toPlainString());
        assertEquals("9999999999999.99", CostAudit.of(d("0.00"), d("9999999999999.99")).change().toPlainString());
        assertEquals("-9999999999999.99", CostAudit.of(d("9999999999999.99"), d("0.00")).change().toPlainString());
    }

    @Test void valueToAbsentOmitsBoth() {
        var audit = CostAudit.of(d("10.00"), null);
        assertNull(audit.resulting());
        assertNull(audit.change());
    }
}
