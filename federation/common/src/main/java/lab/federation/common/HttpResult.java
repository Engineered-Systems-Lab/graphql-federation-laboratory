package lab.federation.common;

/** The result of ONE HTTP call: an answer (status and body) or a failure (no answer). */
public record HttpResult(int status, String body, Throwable failure) {
    public static HttpResult answer(int status, String body) {
        return new HttpResult(status, body, null);
    }

    public static HttpResult failed(Throwable failure) {
        return new HttpResult(0, null, failure);
    }

    public boolean failed() {
        return failure != null;
    }
}
