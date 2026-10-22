package lab.enterprise.missions.xml;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import lab.enterprise.missions.ApiException;
import lab.enterprise.missions.Samples;
import org.junit.jupiter.api.Test;

class CodecParseTest {
    /** The fixture with LF line ends, whatever the checkout converted. */
    private static String sample() { return new String(Samples.postInputBytes(), StandardCharsets.UTF_8).replace("\r\n", "\n"); }

    private static void invalid(byte[] body, String why) {
        var e = assertThrows(ApiException.class, () -> Codec.parseMission(body), why);
        assertEquals(400, e.status, why);
        assertEquals("INVALID_REQUEST", e.code, why);
    }

    private static void invalid(String body, String why) { invalid(body.getBytes(StandardCharsets.UTF_8), why); }

    private static String with(String from, String to) {
        String sample = sample();
        assertTrue(sample.contains(from), from);
        return sample.replace(from, to);
    }

    @Test void theContractExampleParsesWithItsServiceOwnedElementsAbsent() {
        Mission mission = Codec.parseMission(Samples.postInputBytes());
        assertNull(mission.getMissionId());
        assertNull(mission.getLastUpdated());
        assertEquals("43130.05", mission.getStardate());
        assertEquals("8760", mission.getDurationHours());
        assertTrue(mission.getAssignedCrewIds().getCrewId().isEmpty());
    }

    @Test void aByteOrderMarkAndNoDeclarationAreTolerated() {
        ByteArrayOutputStream bom = new ByteArrayOutputStream();
        bom.writeBytes(new byte[] {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF});
        bom.writeBytes(Samples.postInputBytes());
        assertEquals("43130.05", Codec.parseMission(bom.toByteArray()).getStardate());
        String bare = sample().replaceFirst("^<\\?xml[^>]*\\?>\\s*", "");
        assertEquals("43130.05", Codec.parseMission(bare.getBytes(StandardCharsets.UTF_8)).getStardate());
    }

    @Test void textIsPreservedExactlyIncludingWhitespaceAndSupplementaryCharacters() {
        String title = "  🚀 spaced ü  ";
        Mission mission = Codec.parseMission(with("Contract example: minimal planned mission", title).getBytes(StandardCharsets.UTF_8));
        assertEquals(title, mission.getTitle());
    }

    @Test void lengthBoundsCountCodePointsNotUtf16Units() {
        String max = "🚀".repeat(120);
        assertEquals(max, Codec.parseMission(with("Contract example: minimal planned mission", max).getBytes(StandardCharsets.UTF_8)).getTitle());
        invalid(with("Contract example: minimal planned mission", max + "x"), "121 code points");
        String objective = "🚀".repeat(2000);
        assertEquals(objective, Codec.parseMission(with("Illustrative contract example, not a dataset record.", objective).getBytes(StandardCharsets.UTF_8)).getObjective());
        invalid(with("Illustrative contract example, not a dataset record.", objective + "x"), "2001 code points");
    }

    @Test void malformedAndEmptyDocumentsAreInvalid() {
        invalid("", "empty");
        invalid("   ", "blank");
        invalid("<mission", "truncated");
        invalid(sample() + "<x/>", "trailing element");
        invalid(sample().replace("</mission>", ""), "unclosed");
        invalid(new byte[] {'<', 'm', 'i', 's', 's', 'i', 'o', 'n', (byte) 0xC3, (byte) 0x28}, "invalid UTF-8 byte sequence");
    }

    @Test void schemaViolationsAreInvalid() {
        invalid(with("<priority>4</priority>", "<priority>6</priority>"), "priority range");
        invalid(with("<priority>4</priority>", "<priority>04</priority>"), "non-canonical priority");
        invalid(with("<stardate>43130.05</stardate>", "<stardate>43130.1</stardate>"), "stardate spelling");
        invalid(with("<stardate>43130.05</stardate>", "<stardate>49000.00</stardate>"), "stardate range");
        invalid(with("<durationHours>8760</durationHours>", "<durationHours>8761</durationHours>"), "duration range");
        invalid(with("<type>DIPLOMATIC</type>", "<type>diplomatic</type>"), "enum case");
        invalid(with("<type>DIPLOMATIC</type>", "<type>ENGINEERING</type>"), "unknown enum value");
        invalid(with("<status>PLANNED</status>", "<status/>"), "empty status");
        invalid(with("<title>Contract example: minimal planned mission</title>", "<title></title>"), "empty title");
        invalid(with("<priority>4</priority>", "<priority>4</priority><priority>4</priority>"), "excess scalar");
        invalid(with("<priority>4</priority>", ""), "missing required element");
        invalid(with("<assignedCrewIds/>", ""), "missing container");
        invalid(with("<assignedCrewIds/>", "<assignedCrewIds><crewId>P-1</crewId></assignedCrewIds>"), "wrong reference class in crew");
        invalid(with("<participantIds/>", "<participantIds><participantId>C-1</participantId></participantIds>"), "crew in participants");
        invalid(with("<assignedAssetIds/>", "<assignedAssetIds><assetId>sh-17</assetId></assignedAssetIds>"), "asset grammar");
        invalid(with("<assignedCrewIds/>", "<assignedCrewIds><crewId>C-01</crewId></assignedCrewIds>"), "leading zero");
        invalid(with("<assignedCrewIds/>", "<assignedCrewIds>" + "<crewId>C-1</crewId>".repeat(101) + "</assignedCrewIds>"), "more than 100 crew");
        invalid(with("<assignedAssetIds/>", "<assignedAssetIds>" + "<assetId>SH-1</assetId>".repeat(51) + "</assignedAssetIds>"), "more than 50 assets");
    }

    @Test void orderUnknownContentAndNilAreInvalid() {
        invalid(with("<type>DIPLOMATIC</type>\n  <classification>UNCLASSIFIED</classification>", "<classification>UNCLASSIFIED</classification>\n  <type>DIPLOMATIC</type>"), "order");
        invalid(with("<priority>4</priority>", "<priority>4</priority><surprise>x</surprise>"), "unknown element");
        invalid(with("<mission xmlns=\"urn:starfleet:missions:v1\">", "<mission xmlns=\"urn:starfleet:missions:v1\" extra=\"1\">"), "unknown attribute");
        invalid(with("<mission xmlns=\"urn:starfleet:missions:v1\">", "<mission xmlns=\"urn:starfleet:missions:v2\">"), "other namespace");
        invalid(with("<mission xmlns=\"urn:starfleet:missions:v1\">", "<mission>"), "no namespace");
        invalid(with("<priority>4</priority>", "<priority xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:nil=\"true\"/>"), "xsi:nil");
    }

    @Test void theRootMustBeAMission() {
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><error xmlns=\"urn:starfleet:missions:v1\"><code>INVALID_REQUEST</code><message>m</message></error>", "error root");
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><missionList xmlns=\"urn:starfleet:missions:v1\"><page>1</page><pageSize>20</pageSize><totalCount>0</totalCount><totalPages>0</totalPages></missionList>", "list root");
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><other/>", "unknown root");
    }

    @Test void doctypeEntitiesAndExternalResourcesAreNeverProcessed() {
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE mission [<!ENTITY x \"y\">]>" + sample().replaceFirst("^<\\?xml[^>]*\\?>", ""), "internal entity");
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE mission [<!ENTITY x SYSTEM \"file:///etc/passwd\">]>"
                + sample().replaceFirst("^<\\?xml[^>]*\\?>", "").replace("Example location", "&x;"), "external entity");
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE mission SYSTEM \"http://127.0.0.1:9/x.dtd\">"
                + sample().replaceFirst("^<\\?xml[^>]*\\?>", ""), "external DTD");
        invalid("<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE lolz [<!ENTITY a \"aaaaaaaaaa\"><!ENTITY b \"&a;&a;&a;&a;&a;&a;&a;&a;\"><!ENTITY c \"&b;&b;&b;&b;&b;&b;&b;&b;\">]>"
                + sample().replaceFirst("^<\\?xml[^>]*\\?>", "").replace("Example location", "&c;"), "entity expansion");
        invalid(with("Example location", "&undefined;"), "undeclared entity reference");
        // Predefined entities and character references remain ordinary XML.
        assertEquals("a<b&c 🚀", Codec.parseMission(with("Example location", "a&lt;b&amp;c &#x1F680;").getBytes(StandardCharsets.UTF_8)).getLocation().getName());
    }

    @Test void onlyUtf8IsAccepted() {
        invalid(with("encoding=\"UTF-8\"", "encoding=\"ISO-8859-1\""), "latin-1 declaration");
        invalid(with("encoding=\"UTF-8\"", "encoding=\"utf-16\""), "utf-16 declaration");
        invalid(with("encoding=\"UTF-8\"", "encoding=\"US-ASCII\""), "ascii declaration");
        invalid(sample().getBytes(StandardCharsets.UTF_16LE), "UTF-16LE bytes");
        invalid(sample().getBytes(StandardCharsets.UTF_16BE), "UTF-16BE bytes");
        ByteArrayOutputStream utf16 = new ByteArrayOutputStream();
        utf16.writeBytes(new byte[] {(byte) 0xFF, (byte) 0xFE});
        utf16.writeBytes(sample().getBytes(StandardCharsets.UTF_16LE));
        invalid(utf16.toByteArray(), "UTF-16 with a byte order mark");
        assertEquals("43130.05", Codec.parseMission(with("encoding=\"UTF-8\"", "encoding=\"utf-8\"").getBytes(StandardCharsets.UTF_8)).getStardate());
        assertEquals("43130.05", Codec.parseMission(with("encoding=\"UTF-8\"", "encoding='UTF-8'").getBytes(StandardCharsets.UTF_8)).getStardate());
    }

    @Test void theErrorMessageNamesNoParserInternals() {
        var e = assertThrows(ApiException.class, () -> Codec.parseMission(with("<priority>4</priority>", "<priority>6</priority>").getBytes(StandardCharsets.UTF_8)));
        for (String leak : new String[] {"cvc-", "Exception", "xerces", "javax", "org.", "SAX"}) assertFalse(e.getMessage().contains(leak), e.getMessage());
        assertTrue(e.getMessage().startsWith("The request body is not a valid mission document"), e.getMessage());
    }
}
