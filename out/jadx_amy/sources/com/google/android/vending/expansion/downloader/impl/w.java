package com.google.android.vending.expansion.downloader.impl;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.util.Log;

/* compiled from: DownloadsDB.java */
/* loaded from: classes.dex */
public class w extends SQLiteOpenHelper {
    private static final String[][][] a = {v.a, x.a};
    private static final String[] b = {"DownloadColumns", "MetadataColumns"};

    w(Context context) {
        super(context, "DownloadsDB", (SQLiteDatabase.CursorFactory) null, 7);
    }

    private String a(String str, String[][] strArr) {
        StringBuilder sb = new StringBuilder();
        sb.append("CREATE TABLE ");
        sb.append(str);
        sb.append(" (");
        for (String[] strArr2 : strArr) {
            sb.append(' ');
            sb.append(strArr2[0]);
            sb.append(' ');
            sb.append(strArr2[1]);
            sb.append(',');
        }
        sb.setLength(sb.length() - 1);
        sb.append(");");
        return sb.toString();
    }

    private void a(SQLiteDatabase sQLiteDatabase) {
        for (String str : b) {
            try {
                sQLiteDatabase.execSQL("DROP TABLE IF EXISTS " + str);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    @Override // android.database.sqlite.SQLiteOpenHelper
    public void onCreate(SQLiteDatabase sQLiteDatabase) {
        int length = a.length;
        for (int i = 0; i < length; i++) {
            try {
                sQLiteDatabase.execSQL(a(b[i], a[i]));
            } catch (Exception e) {
                while (true) {
                    e.printStackTrace();
                }
            }
        }
    }

    @Override // android.database.sqlite.SQLiteOpenHelper
    public void onUpgrade(SQLiteDatabase sQLiteDatabase, int i, int i2) {
        Log.w(w.class.getName(), "Upgrading database from version " + i + " to " + i2 + ", which will destroy all old data");
        a(sQLiteDatabase);
        onCreate(sQLiteDatabase);
    }
}
