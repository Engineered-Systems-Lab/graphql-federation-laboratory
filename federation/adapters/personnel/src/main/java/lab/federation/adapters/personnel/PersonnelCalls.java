package lab.federation.adapters.personnel;

import java.util.Map;
import java.util.function.Function;
import lab.federation.common.ErrorCode;
import lab.federation.common.HttpResult;
import lab.federation.common.Outcome;

/**
 * Derives the outcome of ONE SOAP call. The Personnel v2 service answers success with HTTP 200 and every declared fault with HTTP 500
 * and one PersonnelServiceFault in the SOAP detail (its code InvalidRequest, PersonnelNotFound, ServiceUnavailable or InternalError).
 *
 * <ul>
 *   <li>200 with a body that reads as the contract: RESOLVED (the parsed value).</li>
 *   <li>500 with the fault PersonnelNotFound: UNRESOLVED (the service says the person does not exist; data, no errors entry).</li>
 *   <li>500 with the fault InvalidRequest: UNAVAILABLE with UPSTREAM_BAD_RESPONSE here (the adapter sent something the service
 *       refuses, which is not the service's outage); the query that took the id from a client reads it first with
 *       {@link #invalidRequest} and reports BAD_USER_INPUT.</li>
 *   <li>a connection failure, a timeout, any other 5xx (the faults ServiceUnavailable and InternalError included): UNAVAILABLE with
 *       SERVICE_UNAVAILABLE.</li>
 *   <li>a 200 that does not read as the contract, or any other status: UNAVAILABLE with UPSTREAM_BAD_RESPONSE.</li>
 * </ul>
 */
final class PersonnelCalls {
    static final String NOT_FOUND_CODE = "PersonnelNotFound";
    static final String INVALID_REQUEST_CODE = "InvalidRequest";

    private PersonnelCalls() {
    }

    static <T> Outcome<T> outcome(HttpResult result, Function<String, T> parse) {
        if (result.failed()) {
            return Outcome.unavailable(ErrorCode.SERVICE_UNAVAILABLE, "Service unavailable");
        }
        int status = result.status();
        if (status == 200) {
            try {
                return Outcome.resolved(parse.apply(result.body()));
            } catch (RuntimeException error) {
                return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service answered a body the adapter cannot use");
            }
        }
        if (status >= 500) {
            PersonnelXml.Fault fault = PersonnelXml.fault(result.body());
            if (fault != null && NOT_FOUND_CODE.equals(fault.code())) {
                return Outcome.unresolved();
            }
            if (fault != null && INVALID_REQUEST_CODE.equals(fault.code())) {
                return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service refused the request");
            }
            return Outcome.unavailable(ErrorCode.SERVICE_UNAVAILABLE, "Service unavailable");
        }
        return Outcome.unavailable(ErrorCode.UPSTREAM_BAD_RESPONSE, "Service answered " + status + " and the adapter cannot use it");
    }

    /** True when the service refused the request with the fault InvalidRequest. */
    static boolean invalidRequest(HttpResult result) {
        if (result.failed() || result.status() < 500) {
            return false;
        }
        PersonnelXml.Fault fault = PersonnelXml.fault(result.body());
        return fault != null && INVALID_REQUEST_CODE.equals(fault.code());
    }

    /** The outcome of GetPersonnelMember for {@code personnelId}: the member, which must be the one asked for. */
    static Outcome<Map<String, Object>> member(HttpResult result, String personnelId) {
        return outcome(result, body -> {
            Map<String, Object> member = PersonnelXml.single(body).member();
            if (!personnelId.equals(member.get("personnelId"))) {
                throw new IllegalArgumentException("the service answered another member");
            }
            return member;
        });
    }
}
