package lab.enterprise.missions;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import lab.enterprise.missions.xml.Codec;
import lab.enterprise.missions.xml.Mission;

/** Test inputs: the contract's own POST example, parsed through the real codec. */
public final class Samples {
    private Samples() { }

    public static byte[] postInputBytes() {
        try {
            return Files.readAllBytes(Path.of("fixtures", "valid", "mission-post-input.xml"));
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** A fresh PLANNED mission with no service-owned element, as a POST body carries it. */
    public static Mission planned() { return Codec.parseMission(postInputBytes()); }
}
