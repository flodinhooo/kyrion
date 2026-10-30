package dev.kyrion.core.knowledge.ingestion;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.text.PDFTextStripper;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Separate heap and deadline: never run hostile PDF parsing inside Core's JVM. */
public final class PdfParserMain {
    public static void main(String[] args) {
        try (var document = Loader.loadPDF(new File(args[0]));
             var output = new DataOutputStream(new BufferedOutputStream(System.out))) {
            if (document.isEncrypted()) { System.exit(21); }
            if (document.getNumberOfPages() > 200) { System.exit(22); }
            output.writeInt(document.getNumberOfPages());
            int total = 0;
            for (int page = 1; page <= document.getNumberOfPages(); page++) {
                var stripper = new PDFTextStripper();
                stripper.setStartPage(page);
                stripper.setEndPage(page);
                var result = new StringBuilder();
                var writer = new Writer() {
                    @Override public void write(char[] chars, int off, int len) {
                        if (result.length() + len > 1_000_000) throw new IllegalStateException();
                        result.append(chars, off, len);
                    }
                    @Override public void flush() {}
                    @Override public void close() {}
                };
                stripper.writeText(document, writer);
                byte[] text = result.toString().getBytes(StandardCharsets.UTF_8);
                total += text.length;
                if (total > 4_000_000) { System.exit(22); }
                output.writeInt(text.length);
                output.write(text);
            }
        } catch (org.apache.pdfbox.pdmodel.encryption.InvalidPasswordException e) {
            System.exit(21);
        } catch (Throwable e) {
            // Do not print filenames, text, parser diagnostics or stack traces.
            System.exit(20);
        }
    }
}
