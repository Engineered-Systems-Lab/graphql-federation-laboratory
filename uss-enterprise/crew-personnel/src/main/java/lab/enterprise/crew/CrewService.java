package lab.enterprise.crew;

import jakarta.jws.WebService;
import lab.enterprise.crew.contract.*;

@WebService(endpointInterface = "lab.enterprise.crew.contract.CrewPersonnelPortType",
    targetNamespace = Xml.NS, serviceName = "CrewPersonnelService", portName = "CrewPersonnelPort")
public final class CrewService implements CrewPersonnelPortType {
    enum Profile { normal, slow, unavailable }
    @FunctionalInterface interface Delay { void sleep(long milliseconds) throws InterruptedException; }
    private final Dataset dataset;
    private final Profile profile;
    private final Delay delay;
    CrewService(Dataset dataset, Profile profile) { this(dataset, profile, Thread::sleep); }
    CrewService(Dataset dataset, Profile profile, Delay delay) {
        this.dataset = dataset; this.profile = profile; this.delay = delay;
    }

    private void applyProfile() throws CrewServiceFaultMessage {
        if (profile == Profile.unavailable) throw Faults.declared("ServiceUnavailable", null);
        if (profile == Profile.slow) {
            try { delay.sleep(2000); }
            catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw Faults.declared("InternalError", null);
            }
        }
    }
    @Override public GetCrewMemberResponseType getCrewMember(GetCrewMemberRequestType request) throws CrewServiceFaultMessage {
        if (request == null || request.getCrewId() == null ||
            !request.getCrewId().matches("CRW-[0-9]{4}") || request.getCrewId().equals("CRW-0000"))
            throw Faults.declared("InvalidRequest", "crewId");
        try {
            applyProfile();
            var member = dataset.records().stream().filter(m -> m.getCrewId().equals(request.getCrewId())).findFirst()
                .orElseThrow(() -> Faults.declared("CrewNotFound", "crewId"));
            var result = new GetCrewMemberResponseType();
            result.setDatasetVersion(dataset.version); result.setCrewMember(member);
            return result;
        } catch (RuntimeException e) { throw Faults.declared("InternalError", null); }
    }
    @Override public ListCrewMembersResponseType listCrewMembers(ListCrewMembersRequestType request) throws CrewServiceFaultMessage {
        if (request == null) throw Faults.declared("InvalidRequest", null);
        int offset = request.getOffset() == null ? 0 : request.getOffset();
        int limit = request.getLimit() == null ? 20 : request.getLimit();
        if (offset < 0) throw Faults.declared("InvalidRequest", "offset");
        if (limit < 1 || limit > 100) throw Faults.declared("InvalidRequest", "limit");
        try {
            applyProfile();
            var matches = dataset.records().stream()
                .filter(m -> request.getDepartment() == null || m.getDepartment() == request.getDepartment())
                .filter(m -> request.getDutyStatus() == null || m.getDutyStatus() == request.getDutyStatus()).toList();
            var result = new ListCrewMembersResponseType();
            result.setDatasetVersion(dataset.version);
            result.getCrewMember().addAll(matches.stream().skip(offset).limit(limit).toList());
            result.setTotalCount(matches.size()); result.setOffset(offset); result.setLimit(limit);
            result.setHasMore((long) offset + result.getCrewMember().size() < matches.size());
            return result;
        } catch (RuntimeException e) { throw Faults.declared("InternalError", null); }
    }
}
