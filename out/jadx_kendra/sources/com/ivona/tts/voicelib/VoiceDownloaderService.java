package com.ivona.tts.voicelib;

import com.google.android.vending.expansion.downloader.impl.DownloaderService;

/* loaded from: classes.dex */
public class VoiceDownloaderService extends DownloaderService {
    private static final byte[] g = {-103, 116, 89, -42, -114, 69, 74, -65, -101, 19, 103, -63, -118, -49, -120, -2, -108, -79, -37, -127, 111, -90, -24, 10, 2, -50, -62, 66, -110, 18};

    @Override // com.google.android.vending.expansion.downloader.impl.DownloaderService
    public String j() {
        return VoiceDwnldAlarmReceiver.class.getName();
    }

    @Override // com.google.android.vending.expansion.downloader.impl.DownloaderService
    public String h() {
        return "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAipWjiqMwmVmWPrGXTAOY5m3aTNScWGtigFhfnIjIP0JBoMbuXnsVN+L/4sifcq3hSNTVTQimIWqodl0ZvFlmBjpcLq1dbVpVzZRy3VhpDVe38xGCXQGI6C9WR/UsuRXPReKC/dRfeyl9a+qPpvjrAWeQBesmEUwG6D0RqklkjiCp9+0gcEwlO+Q2VG+B51ktzxaU5cV0t2AZJz9MLp+gRJ2eNRjt17cg05yOppM9+LxSJ/l+TqzLOyX9HtSFnAS7eYf8Sm+a8EUmCMh47VbE8+/CIscmMMIT1qet87+Jfh232w2deRFrwa5cYEgsMb54/eO31ky0ZZAiW97uNstttwIDAQAB";
    }

    @Override // com.google.android.vending.expansion.downloader.impl.DownloaderService
    public byte[] i() {
        return g;
    }
}
