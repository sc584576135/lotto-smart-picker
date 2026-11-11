package com.yg.lotto;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 原生 HTTP 桥 + 文件导出。
 * WebView 加载的是 file:///android_asset/index.html，属于不透明来源，
 * 直接 fetch 跨域会被同源策略拦掉，因此把网络请求交给 Java 侧执行；
 * 文件导出走 MediaStore（Android 10+）/ 应用外部目录（旧系统）。
 * JavascriptInterface 的方法在私有后台线程被调用，可以同步阻塞。
 */
public class NetBridge {

    private static final int TIMEOUT = 12000;
    private final Context ctx;

    public NetBridge(Context ctx) {
        this.ctx = ctx;
    }

    @JavascriptInterface
    public String fetch(String url) {
        return request(url, "GET", null, null);
    }

    @JavascriptInterface
    public String post(String url, String headersJson, String body) {
        return request(url, "POST", headersJson, body);
    }

    /** 把文本内容保存为文件。返回 {"ok":"Downloads/xxx"} 或 {"__error":"..."} */
    @JavascriptInterface
    public String saveFile(String filename, String content) {
        try {
            byte[] data = content.getBytes("UTF-8");
            if (Build.VERSION.SDK_INT >= 29) {
                ContentValues values = new ContentValues();
                values.put(MediaStore.Downloads.DISPLAY_NAME, filename);
                values.put(MediaStore.Downloads.MIME_TYPE, "application/json");
                values.put(MediaStore.Downloads.IS_PENDING, 1);
                ContentResolver cr = ctx.getContentResolver();
                Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (uri == null) return "{\"__error\":\"无法写入下载目录\"}";
                OutputStream os = cr.openOutputStream(uri);
                os.write(data);
                os.flush();
                os.close();
                values.clear();
                values.put(MediaStore.Downloads.IS_PENDING, 0);
                cr.update(uri, values, null, null);
                return "{\"ok\":\"下载目录/" + filename + "\"}";
            }
            File dir = ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            if (dir == null) dir = ctx.getFilesDir();
            File f = new File(dir, filename);
            FileOutputStream fos = new FileOutputStream(f);
            fos.write(data);
            fos.close();
            return "{\"ok\":\"" + f.getAbsolutePath().replace("\\", "/") + "\"}";
        } catch (Exception e) {
            String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
            msg = msg.replace("\\", "\\\\").replace("\"", "\\\"")
                     .replace("\n", " ").replace("\r", " ");
            return "{\"__error\":\"" + msg + "\"}";
        }
    }

    private String request(String url, String method, String headersJson, String body) {
        HttpURLConnection conn = null;
        try {
            URL u = new URL(url);
            conn = (HttpURLConnection) u.openConnection();
            conn.setRequestMethod(method);
            conn.setConnectTimeout(TIMEOUT);
            conn.setReadTimeout(TIMEOUT);
            conn.setInstanceFollowRedirects(true);
            conn.setRequestProperty("User-Agent",
                    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0 Mobile Safari/537.36");
            conn.setRequestProperty("Referer", "https://static.sporttery.cn/");
            conn.setRequestProperty("Accept", "application/json, text/plain, */*");

            if (headersJson != null && headersJson.length() > 2) {
                org.json.JSONObject hdrs = new org.json.JSONObject(headersJson);
                java.util.Iterator<String> keys = hdrs.keys();
                while (keys.hasNext()) {
                    String k = keys.next();
                    String v = hdrs.optString(k);
                    if (v != null && v.length() > 0) {
                        conn.setRequestProperty(k, v);
                    }
                }
            }

            if ("POST".equals(method) && body != null) {
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                java.io.OutputStream os = conn.getOutputStream();
                os.write(body.getBytes("UTF-8"));
                os.flush();
                os.close();
            }

            int code = conn.getResponseCode();
            if (code != 200) {
                return "{\"__error\":\"HTTP " + code + "\"}";
            }

            InputStream in = conn.getInputStream();
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) bos.write(buf, 0, n);
            in.close();
            return bos.toString("UTF-8");
        } catch (Exception e) {
            String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
            msg = msg.replace("\\", "\\\\").replace("\"", "\\\"")
                     .replace("\n", " ").replace("\r", " ");
            return "{\"__error\":\"" + msg + "\"}";
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
