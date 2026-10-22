package lab.federation.adapters.mapping;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** The mapping subgraph. It holds no database and makes no outbound call: every answer comes from the release files. */
@SpringBootApplication
public class MappingAdapterApplication {
    public static void main(String[] args) {
        SpringApplication.run(MappingAdapterApplication.class, args);
    }
}
