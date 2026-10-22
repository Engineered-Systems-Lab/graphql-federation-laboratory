package lab.federation.common;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;

/** Reads the JSON object a service answered. */
public final class Json {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private Json() {
    }

    /** The body as a JSON object; anything else (an array, a scalar, malformed text) is an IllegalArgumentException. */
    public static Map<String, Object> object(String body) {
        if (body == null) {
            throw new IllegalArgumentException("empty body");
        }
        try {
            return MAPPER.readValue(body, new TypeReference<Map<String, Object>>() {
            });
        } catch (JsonProcessingException error) {
            throw new IllegalArgumentException("not a JSON object", error);
        }
    }
}
