package lab.enterprise.missions.domain;

/** Code-point text rules of the Missions contract, never UTF-16 chars. */
public final class Text {
    private Text() { }

    /**
     * The contract's pinned whitespace set: Character.isWhitespace as of JDK 17. It is listed here rather than
     * delegated so a later JDK cannot change the contract.
     */
    public static boolean whitespace(int codePoint) {
        return codePoint >= 0x09 && codePoint <= 0x0D || codePoint >= 0x1C && codePoint <= 0x20 || codePoint == 0x1680
                || codePoint >= 0x2000 && codePoint <= 0x2006 || codePoint >= 0x2008 && codePoint <= 0x200A
                || codePoint == 0x2028 || codePoint == 0x2029 || codePoint == 0x205F || codePoint == 0x3000;
    }

    /** True when the text has no non-whitespace code point (an empty text included). */
    public static boolean blank(String text) { return text.codePoints().allMatch(Text::whitespace); }

    /** XML 1.0 Char production: what a representation can carry. */
    public static boolean xmlChar(int codePoint) {
        return codePoint == 0x9 || codePoint == 0xA || codePoint == 0xD || codePoint >= 0x20 && codePoint <= 0xD7FF
                || codePoint >= 0xE000 && codePoint <= 0xFFFD || codePoint >= 0x10000 && codePoint <= 0x10FFFF;
    }

    public static int length(String text) { return text.codePointCount(0, text.length()); }

    /** The UTF-8 length in bytes: what a BYTE-semantics column stores, never the character count. */
    public static int utf8Length(String text) { return text.getBytes(java.nio.charset.StandardCharsets.UTF_8).length; }
}
