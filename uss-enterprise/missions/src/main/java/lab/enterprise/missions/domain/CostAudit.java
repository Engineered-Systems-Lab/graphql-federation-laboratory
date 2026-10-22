package lab.enterprise.missions.domain;

import java.math.BigDecimal;

/**
 * The audit population rule for one cost field, applied independently to estimated and actual cost:
 * absent to absent omits both, absent to value records only the value, value to value records the value and the signed
 * difference (0.00 when unchanged), value to absent omits both. Absence is never zero.
 */
public record CostAudit(BigDecimal resulting, BigDecimal change) {
    public static CostAudit of(BigDecimal before, BigDecimal after) {
        if (after == null) return new CostAudit(null, null);
        if (before == null) return new CostAudit(after, null);
        return new CostAudit(after, after.subtract(before).setScale(2));
    }
}
