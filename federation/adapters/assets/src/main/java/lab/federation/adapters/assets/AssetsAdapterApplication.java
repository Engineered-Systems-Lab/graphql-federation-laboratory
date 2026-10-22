package lab.federation.adapters.assets;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** The Assets subgraph. It holds no state and no database: every answer comes from one call to the Assets service. */
@SpringBootApplication
public class AssetsAdapterApplication {
    public static void main(String[] args) {
        SpringApplication.run(AssetsAdapterApplication.class, args);
    }
}
