package lab.enterprise.missions;

import java.nio.file.Files;
import java.nio.file.Path;
import lab.enterprise.missions.api.MissionsApplication;
import lab.enterprise.missions.api.MissionsServlet;
import lab.enterprise.missions.api.XmlErrorReportValve;
import lab.enterprise.missions.repository.Database;
import lab.enterprise.missions.repository.MissionRepository;
import org.apache.catalina.Context;
import org.apache.catalina.connector.Connector;
import org.apache.catalina.startup.Tomcat;

/** Native entry point: Tomcat hosting the Jersey application. The image and compose deployment package it (see the Dockerfile). */
public final class Main {
    private Main() { }

    public static void main(String[] args) throws Exception {
        Config config = Config.fromEnvironment(System.getenv());
        Database database = new Database(config);
        Path base = Files.createTempDirectory("missions-tomcat");
        var tomcat = new Tomcat();
        tomcat.setBaseDir(base.toString());
        Connector connector = tomcat.getConnector();
        connector.setPort(config.port());
        connector.setProperty("address", config.bindHost());
        // Let unusual query characters reach the contract's own validation (400 INVALID_REQUEST with an XML body).
        connector.setProperty("relaxedQueryChars", "\"<>[\\]^`{|}");
        XmlErrorReportValve.install(tomcat);
        Context context = tomcat.addContext("", base.toString());
        Tomcat.addServlet(context, "missions", new MissionsServlet(new MissionsApplication(new MissionRepository(database))));
        context.addServletMappingDecoded("/*", "missions");
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try { tomcat.stop(); tomcat.destroy(); } catch (Exception ignored) { }
            database.close();
        }));
        tomcat.start();
        System.out.println("Missions: http://" + config.bindHost() + ":" + config.port() + "/missions schema=" + config.dbSchema());
        tomcat.getServer().await();
    }
}
