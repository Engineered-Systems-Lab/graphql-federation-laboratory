package lab.enterprise.personnel;

import jakarta.jws.WebService;
import lab.enterprise.personnel.contract.*;

@WebService(endpointInterface = "lab.enterprise.personnel.contract.PersonnelPortType",
    targetNamespace = Xml.NS, serviceName = "PersonnelService", portName = "PersonnelPort")
public final class PersonnelService implements PersonnelPortType {
    enum Profile { normal, slow, unavailable }
    @FunctionalInterface interface Delay { void sleep(long milliseconds) throws InterruptedException; }
    private final Dataset dataset;
    private final Profile profile;
    private final Delay delay;
    PersonnelService(Dataset dataset, Profile profile) { this(dataset, profile, Thread::sleep); }
    PersonnelService(Dataset dataset, Profile profile, Delay delay) {
        this.dataset = dataset; this.profile = profile; this.delay = delay;
    }

    private void applyProfile() throws PersonnelServiceFaultMessage {
        if (profile == Profile.unavailable) throw Faults.declared("ServiceUnavailable", null);
        if (profile == Profile.slow) {
            try { delay.sleep(2000); }
            catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw Faults.declared("InternalError", null);
            }
        }
    }
    @Override public GetPersonnelMemberResponseType getPersonnelMember(GetPersonnelMemberRequestType request) throws PersonnelServiceFaultMessage {
        if (request == null || request.getPersonnelId() == null ||
            !request.getPersonnelId().matches("PRS-[0-9]{4}") || request.getPersonnelId().equals("PRS-0000"))
            throw Faults.declared("InvalidRequest", "personnelId");
        try {
            applyProfile();
            var member = dataset.records().stream().filter(m -> m.getPersonnelId().equals(request.getPersonnelId())).findFirst()
                .orElseThrow(() -> Faults.declared("PersonnelNotFound", "personnelId"));
            var result = new GetPersonnelMemberResponseType();
            result.setDatasetVersion(dataset.version); result.setPersonnelMember(member);
            return result;
        } catch (RuntimeException e) { throw Faults.declared("InternalError", null); }
    }
    @Override public ListPersonnelMembersResponseType listPersonnelMembers(ListPersonnelMembersRequestType request) throws PersonnelServiceFaultMessage {
        if (request == null) throw Faults.declared("InvalidRequest", null);
        int offset = request.getOffset() == null ? 0 : request.getOffset();
        int limit = request.getLimit() == null ? 20 : request.getLimit();
        if (offset < 0) throw Faults.declared("InvalidRequest", "offset");
        if (limit < 1 || limit > 100) throw Faults.declared("InvalidRequest", "limit");
        try {
            applyProfile();
            var matches = dataset.records().stream()
                .filter(m -> request.getDepartment() == null || (m.getCrewDetails() != null && m.getCrewDetails().getDepartment() == request.getDepartment()))
                .filter(m -> request.getDutyStatus() == null || m.getDutyStatus() == request.getDutyStatus()).toList();
            var result = new ListPersonnelMembersResponseType();
            result.setDatasetVersion(dataset.version);
            result.getPersonnelMember().addAll(matches.stream().skip(offset).limit(limit).toList());
            result.setTotalCount(matches.size()); result.setOffset(offset); result.setLimit(limit);
            result.setHasMore((long) offset + result.getPersonnelMember().size() < matches.size());
            return result;
        } catch (RuntimeException e) { throw Faults.declared("InternalError", null); }
    }
}
