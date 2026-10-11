package com.google.tts;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.net.Uri;

/* loaded from: classes.dex */
public class TTSVersionAlert extends AlertDialog.Builder {
    private static final String INSTALL_TTS = "Install the TTS";
    private static final String MARKET_URI = "market://search?q=pname:com.google.tts";
    private static final String NO_TTS = "This application can talk using the text-to-speech (TTS) library. Please install the TTS.";
    private static final String QUIT = "Do not install the TTS";
    private Activity parent;

    public TTSVersionAlert(Context context, String str, String str2, String str3) {
        super(context);
        this.parent = (Activity) context;
        if (str != null) {
            setMessage(str);
        } else {
            setMessage(NO_TTS);
        }
        DialogInterface.OnClickListener onClickListener = new DialogInterface.OnClickListener() { // from class: com.google.tts.TTSVersionAlert.1
            @Override // android.content.DialogInterface.OnClickListener
            public void onClick(DialogInterface dialogInterface, int i) {
                TTSVersionAlert.this.parent.startActivity(new Intent("android.intent.action.VIEW", Uri.parse(TTSVersionAlert.MARKET_URI)));
            }
        };
        DialogInterface.OnClickListener onClickListener2 = new DialogInterface.OnClickListener() { // from class: com.google.tts.TTSVersionAlert.2
            @Override // android.content.DialogInterface.OnClickListener
            public void onClick(DialogInterface dialogInterface, int i) {
            }
        };
        if (str2 != null) {
            setPositiveButton(str2, onClickListener);
        } else {
            setPositiveButton(INSTALL_TTS, onClickListener);
        }
        if (str3 != null) {
            setNegativeButton(str3, onClickListener2);
        } else {
            setNegativeButton(QUIT, onClickListener2);
        }
    }
}
