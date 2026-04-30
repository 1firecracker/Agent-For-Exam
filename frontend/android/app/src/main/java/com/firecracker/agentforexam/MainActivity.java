package com.firecracker.agentforexam;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import com.getcapacitor.BridgeActivity;

import java.io.File;
import java.io.FileOutputStream;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().addJavascriptInterface(new AndroidFileSaver(this), "AndroidFileSaver");
        }
    }

    public static class AndroidFileSaver {
        private final Activity activity;

        AndroidFileSaver(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void savePdf(String base64, String filename) {
            try {
                byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                File dir = new File(activity.getCacheDir(), "exports");
                if (!dir.exists()) {
                    dir.mkdirs();
                }

                String safeName = sanitizeFilename(filename);
                File file = new File(dir, safeName);
                try (FileOutputStream output = new FileOutputStream(file)) {
                    output.write(bytes);
                }

                Uri uri = FileProvider.getUriForFile(
                    activity,
                    activity.getPackageName() + ".fileprovider",
                    file
                );

                activity.runOnUiThread(() -> openPdf(uri, safeName));
            } catch (Exception error) {
                activity.runOnUiThread(() ->
                    Toast.makeText(activity, "PDF 导出失败：" + error.getMessage(), Toast.LENGTH_LONG).show()
                );
            }
        }

        private void openPdf(Uri uri, String filename) {
            Intent viewIntent = new Intent(Intent.ACTION_VIEW);
            viewIntent.setDataAndType(uri, "application/pdf");
            viewIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

            try {
                activity.startActivity(Intent.createChooser(viewIntent, "打开 PDF"));
                Toast.makeText(activity, "PDF 已生成：" + filename, Toast.LENGTH_SHORT).show();
            } catch (ActivityNotFoundException error) {
                Intent shareIntent = new Intent(Intent.ACTION_SEND);
                shareIntent.setType("application/pdf");
                shareIntent.putExtra(Intent.EXTRA_STREAM, uri);
                shareIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                try {
                    activity.startActivity(Intent.createChooser(shareIntent, "分享 PDF"));
                    Toast.makeText(activity, "PDF 已生成：" + filename, Toast.LENGTH_SHORT).show();
                } catch (ActivityNotFoundException shareError) {
                    Toast.makeText(activity, "PDF 已生成，但没有可打开 PDF 的应用", Toast.LENGTH_LONG).show();
                }
            }
        }

        private String sanitizeFilename(String filename) {
            String fallback = "cheatsheet.pdf";
            String value = filename == null || filename.trim().isEmpty() ? fallback : filename.trim();
            value = value.replaceAll("[^a-zA-Z0-9._-]", "_");
            if (!value.toLowerCase().endsWith(".pdf")) {
                value = value + ".pdf";
            }
            return value;
        }
    }
}
