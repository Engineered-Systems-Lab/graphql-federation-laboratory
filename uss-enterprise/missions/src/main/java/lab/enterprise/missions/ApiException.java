package lab.enterprise.missions;

/** A deterministic API failure: HTTP status plus the contract error code. The message is never parsed by clients. */
public final class ApiException extends RuntimeException {
    public final int status;
    public final String code;

    public ApiException(int status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public static ApiException invalidRequest(String message) {
        return new ApiException(400, "INVALID_REQUEST", message);
    }
}
