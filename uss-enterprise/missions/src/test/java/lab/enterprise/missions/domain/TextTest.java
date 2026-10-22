package lab.enterprise.missions.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class TextTest {
    /** The pinned list of the design, written out independently of the implementation under test. */
    private static final int[] PINNED = {0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x1680, 0x2000, 0x2001, 0x2002,
            0x2003, 0x2004, 0x2005, 0x2006, 0x2008, 0x2009, 0x200A, 0x2028, 0x2029, 0x205F, 0x3000};

    @Test void whitespaceIsExactlyThePinnedSet() {
        int count = 0;
        for (int cp = 0; cp <= Character.MAX_CODE_POINT; cp++) {
            boolean pinned = false;
            for (int p : PINNED) pinned |= p == cp;
            assertEquals(pinned, Text.whitespace(cp), "U+" + Integer.toHexString(cp));
            if (pinned) count++;
        }
        assertEquals(PINNED.length, count);
    }

    @Test void whitespaceAgreesWithTheJdkBaselineOfThePinnedSet() {
        // The design pins Character.isWhitespace as of JDK 17 and states it is unchanged through later JDKs.
        for (int cp = 0; cp <= Character.MAX_CODE_POINT; cp++)
            assertEquals(Character.isWhitespace(cp), Text.whitespace(cp), "U+" + Integer.toHexString(cp));
    }

    @Test void nonBreakingAndZeroWidthSpacesAreNotWhitespace() {
        for (int cp : new int[] {0xA0, 0x2007, 0x202F, 0x85, 0x200B, 0xFEFF}) assertFalse(Text.whitespace(cp), "U+" + Integer.toHexString(cp));
    }

    @Test void blankMeansNoNonWhitespaceCodePoint() {
        assertTrue(Text.blank(""));
        assertTrue(Text.blank(" \t　 "));
        assertFalse(Text.blank(" a "));
        assertFalse(Text.blank(" "));
        assertFalse(Text.blank("🚀"));
    }

    @Test void lengthCountsCodePointsNotUtf16Units() {
        assertEquals(3, Text.length("a🚀b"));
        assertEquals(4, "a🚀b".length());
    }

    @Test void xmlCharsAreTheXml10Production() {
        for (int cp : new int[] {0x9, 0xA, 0xD, 0x20, 0xD7FF, 0xE000, 0xFFFD, 0x10000, 0x10FFFF}) assertTrue(Text.xmlChar(cp), "U+" + Integer.toHexString(cp));
        for (int cp : new int[] {0x0, 0x8, 0xB, 0xC, 0xE, 0x1F, 0xD800, 0xDFFF, 0xFFFE, 0xFFFF, 0x110000}) assertFalse(Text.xmlChar(cp), "U+" + Integer.toHexString(cp));
    }

    @Test void utf8LengthCountsBytesNotCharacters() {
        assertEquals(3, Text.utf8Length("C-1"));
        assertEquals(2, Text.utf8Length(new String(Character.toChars(0xE9))));
        assertEquals(4, Text.utf8Length(new String(Character.toChars(0x1F680))));
        assertEquals(0, Text.utf8Length(""));
    }
}
