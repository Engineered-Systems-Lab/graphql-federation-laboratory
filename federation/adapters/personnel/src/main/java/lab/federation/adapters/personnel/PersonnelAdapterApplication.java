package lab.federation.adapters.personnel;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** The Personnel subgraph. It holds no state and no database: every answer comes from one call to the Personnel v2 service. */
@SpringBootApplication
public class PersonnelAdapterApplication {
    public static void main(String[] args) {
        SpringApplication.run(PersonnelAdapterApplication.class, args);
    }
}
