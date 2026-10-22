package lab.enterprise.crew;

import javax.xml.namespace.QName;
import org.apache.cxf.Bus;
import org.apache.cxf.BusFactory;
import org.apache.cxf.endpoint.Server;
import org.apache.cxf.jaxws.JaxWsServerFactoryBean;
import lab.enterprise.crew.contract.CrewPersonnelPortType;

public final class Main {
    private Main() { }
    static Server publish(Bus bus, String address, CrewService service) {
        var factory = new JaxWsServerFactoryBean();
        factory.setBus(bus);
        factory.setServiceClass(CrewPersonnelPortType.class);
        factory.setServiceBean(service);
        factory.setWsdlURL(Main.class.getResource("/deployment.wsdl").toExternalForm());
        factory.setServiceName(new QName(Xml.NS, "CrewPersonnelService"));
        factory.setEndpointName(new QName(Xml.NS, "CrewPersonnelPort"));
        factory.setAddress(address);
        factory.getInInterceptors().add(new RequestValidation());
        factory.getOutFaultInterceptors().add(new FaultMapping());
        return factory.create();
    }
    public static void main(String[] args) throws Exception {
        String version = env("CREW_DATASET_VERSION", Dataset.DEFAULT_VERSION);
        var profile = CrewService.Profile.valueOf(env("CREW_FAILURE_PROFILE", "normal"));
        int port = Integer.parseInt(env("CREW_PORT", "8081"));
        if (port < 1 || port > 65535) throw new IllegalArgumentException("CREW_PORT must be 1..65535");
        String host = env("CREW_BIND_HOST", "127.0.0.1");
        if (!host.equals("127.0.0.1") && !host.equals("0.0.0.0"))
            throw new IllegalArgumentException("CREW_BIND_HOST must be 127.0.0.1 or 0.0.0.0");
        var dataset = Dataset.load(version);
        var bus = BusFactory.newInstance().createBus();
        String address = "http://" + host + ":" + port + "/soap/crew-personnel";
        var server = publish(bus, address, new CrewService(dataset, profile));
        Runtime.getRuntime().addShutdownHook(new Thread(() -> { server.destroy(); bus.shutdown(true); }));
        System.out.println("Crew & Personnel: " + address + " dataset=" + version + " profile=" + profile);
    }
    private static String env(String key, String fallback) {
        String value = System.getenv(key); return value == null ? fallback : value;
    }
}
