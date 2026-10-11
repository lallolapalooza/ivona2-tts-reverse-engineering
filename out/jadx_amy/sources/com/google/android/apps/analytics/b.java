package com.google.android.apps.analytics;

import android.content.ContentValues;
import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

/* loaded from: classes.dex */
class b extends SQLiteOpenHelper {
    public b(Context context) {
        super(context, "google_analytics.db", (SQLiteDatabase.CursorFactory) null, 2);
    }

    private void a(SQLiteDatabase sQLiteDatabase) {
        sQLiteDatabase.execSQL("DROP TABLE IF EXISTS custom_variables");
        sQLiteDatabase.execSQL("CREATE TABLE custom_variables (" + String.format(" '%s' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,", "cv_id") + String.format(" '%s' INTEGER NOT NULL,", "event_id") + String.format(" '%s' INTEGER NOT NULL,", "cv_index") + String.format(" '%s' CHAR(64) NOT NULL,", "cv_name") + String.format(" '%s' CHAR(64) NOT NULL,", "cv_value") + String.format(" '%s' INTEGER NOT NULL);", "cv_scope"));
        sQLiteDatabase.execSQL("DROP TABLE IF EXISTS custom_var_cache");
        sQLiteDatabase.execSQL("CREATE TABLE custom_var_cache (" + String.format(" '%s' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,", "cv_id") + String.format(" '%s' INTEGER NOT NULL,", "event_id") + String.format(" '%s' INTEGER NOT NULL,", "cv_index") + String.format(" '%s' CHAR(64) NOT NULL,", "cv_name") + String.format(" '%s' CHAR(64) NOT NULL,", "cv_value") + String.format(" '%s' INTEGER NOT NULL);", "cv_scope"));
        for (int i = 1; i <= 5; i++) {
            ContentValues contentValues = new ContentValues();
            contentValues.put("event_id", (Integer) 0);
            contentValues.put("cv_index", Integer.valueOf(i));
            contentValues.put("cv_name", "");
            contentValues.put("cv_scope", (Integer) 3);
            contentValues.put("cv_value", "");
            sQLiteDatabase.insert("custom_var_cache", "event_id", contentValues);
        }
    }

    @Override // android.database.sqlite.SQLiteOpenHelper
    public void onCreate(SQLiteDatabase sQLiteDatabase) {
        sQLiteDatabase.execSQL("CREATE TABLE events (" + String.format(" '%s' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,", "event_id") + String.format(" '%s' INTEGER NOT NULL,", "user_id") + String.format(" '%s' CHAR(256) NOT NULL,", "account_id") + String.format(" '%s' INTEGER NOT NULL,", "random_val") + String.format(" '%s' INTEGER NOT NULL,", "timestamp_first") + String.format(" '%s' INTEGER NOT NULL,", "timestamp_previous") + String.format(" '%s' INTEGER NOT NULL,", "timestamp_current") + String.format(" '%s' INTEGER NOT NULL,", "visits") + String.format(" '%s' CHAR(256) NOT NULL,", "category") + String.format(" '%s' CHAR(256) NOT NULL,", "action") + String.format(" '%s' CHAR(256), ", "label") + String.format(" '%s' INTEGER,", "value") + String.format(" '%s' INTEGER,", "screen_width") + String.format(" '%s' INTEGER);", "screen_height"));
        sQLiteDatabase.execSQL("CREATE TABLE session (" + String.format(" '%s' INTEGER PRIMARY KEY,", "timestamp_first") + String.format(" '%s' INTEGER NOT NULL,", "timestamp_previous") + String.format(" '%s' INTEGER NOT NULL,", "timestamp_current") + String.format(" '%s' INTEGER NOT NULL,", "visits") + String.format(" '%s' INTEGER NOT NULL);", "store_id"));
        sQLiteDatabase.execSQL("CREATE TABLE install_referrer (referrer TEXT PRIMARY KEY NOT NULL);");
        a(sQLiteDatabase);
    }

    @Override // android.database.sqlite.SQLiteOpenHelper
    public void onUpgrade(SQLiteDatabase sQLiteDatabase, int i, int i2) {
        if (i2 == 2) {
            a(sQLiteDatabase);
        }
    }
}
