package lab.federation.adapters.missions;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** The Missions subgraph. It holds no state and no database: every answer comes from calls to the Missions service. */
@SpringBootApplication
public class MissionsAdapterApplication {
    public static void main(String[] args) {
        SpringApplication.run(MissionsAdapterApplication.class, args);
    }
}
