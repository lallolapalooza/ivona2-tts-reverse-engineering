package com.google.android.apps.analytics;

import android.content.ContentValues;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteException;
import android.database.sqlite.SQLiteStatement;
import android.util.Log;

/* loaded from: classes.dex */
class a {
    private b a;
    private SQLiteStatement b = null;

    a(b bVar) {
        this.a = bVar;
        try {
            bVar.getWritableDatabase().close();
        } catch (SQLiteException e) {
            Log.e("googleanalytics", e.toString());
        }
    }

    public void a(String str) {
        try {
            SQLiteDatabase writableDatabase = this.a.getWritableDatabase();
            ContentValues contentValues = new ContentValues();
            contentValues.put("referrer", str);
            writableDatabase.insert("install_referrer", null, contentValues);
        } catch (SQLiteException e) {
            Log.e("googleanalytics", e.toString());
        }
    }
}
