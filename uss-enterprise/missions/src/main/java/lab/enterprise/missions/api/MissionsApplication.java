package lab.enterprise.missions.api;

import lab.enterprise.missions.repository.MissionRepository;
import org.glassfish.hk2.utilities.binding.AbstractBinder;
import org.glassfish.jersey.server.ResourceConfig;
import org.glassfish.jersey.server.ServerProperties;

/** Jersey wiring: our own filter, mapper and resource only, with every framework default that could alter a status switched off. */
public final class MissionsApplication extends ResourceConfig {
    public MissionsApplication(MissionRepository repository) {
        register(new AbstractBinder() {
            @Override protected void configure() { bind(repository).to(MissionRepository.class); }
        });
        register(MissionsResource.class);
        register(RouteFilter.class);
        register(ErrorMapper.class);
        // Keep bodyless statuses bodyless: without this the container writes its own HTML error page.
        property(ServerProperties.RESPONSE_SET_STATUS_OVER_SEND_ERROR, true);
        property(ServerProperties.WADL_FEATURE_DISABLE, true);
        property(ServerProperties.FEATURE_AUTO_DISCOVERY_DISABLE, true);
        // The design's Location is the relative path /missions/{id}; do not let Jersey rewrite it to an absolute URI.
        property(ServerProperties.LOCATION_HEADER_RELATIVE_URI_RESOLUTION_DISABLED, true);
    }
}
