package com.ivona.tts.voicelib;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

/* loaded from: classes.dex */
public abstract class UpdateReceiverLib extends BroadcastReceiver {
    protected abstract Intent a(Context context);

    @Override // android.content.BroadcastReceiver
    public void onReceive(Context context, Intent intent) {
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("UpdateReceiver", "onReceive");
        }
        Bundle extras = intent.getExtras();
        if (extras != null && extras.containsKey("android.intent.extra.UID")) {
            String[] packagesForUid = context.getPackageManager().getPackagesForUid(extras.getInt("android.intent.extra.UID"));
            if (packagesForUid != null && packagesForUid.length > 0) {
                String str = packagesForUid[0];
                if (com.ivona.tts.commonlib.a.c) {
                    Log.d("UpdateReceiver", "onReceive data " + (str != null ? str : ""));
                }
                if (!str.equals(com.ivona.tts.commonlib.c.a(context).packageName)) {
                    return;
                }
            }
        }
        if (com.ivona.tts.commonlib.a.c) {
            Log.d("UpdateReceiver", "onReceive updated!");
        }
        if (!VoiceFiles.a(context)) {
            NotificationManager notificationManager = (NotificationManager) context.getSystemService("notification");
            Notification notification = new Notification(l.a, context.getString(p.h), System.currentTimeMillis());
            notification.flags |= 16;
            Intent a = a(context);
            a.setFlags(131072);
            notification.setLatestEventInfo(context.getApplicationContext(), context.getString(p.a), context.getString(p.h), PendingIntent.getActivity(context, 0, a, 0));
            notificationManager.notify(2, notification);
        }
    }
}
