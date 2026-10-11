package com.google.android.vending.expansion.downloader.impl;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteDoneException;
import android.database.sqlite.SQLiteException;
import android.database.sqlite.SQLiteOpenHelper;
import android.database.sqlite.SQLiteStatement;

/* compiled from: DownloadsDB.java */
/* loaded from: classes.dex */
public class u {
    private static u i;
    final SQLiteOpenHelper b;
    SQLiteStatement c;
    SQLiteStatement d;
    long e;
    int f;
    int g;
    int h;
    public static final String a = u.class.getName();
    private static final String[] j = {"FN", "URI", "ETAG", "TOTALBYTES", "CURRENTBYTES", "LASTMOD", "STATUS", "CONTROL", "FAILCOUNT", "RETRYAFTER", "REDIRECTCOUNT", "FILEIDX"};

    public static synchronized u a(Context context) {
        u uVar;
        synchronized (u.class) {
            uVar = i == null ? new u(context) : i;
        }
        return uVar;
    }

    private SQLiteStatement b() {
        if (this.c == null) {
            this.c = this.b.getReadableDatabase().compileStatement("SELECT _id FROM DownloadColumns WHERE FILEIDX = ?");
        }
        return this.c;
    }

    private SQLiteStatement c() {
        if (this.d == null) {
            this.d = this.b.getReadableDatabase().compileStatement("UPDATE DownloadColumns SET CURRENTBYTES = ? WHERE FILEIDX = ?");
        }
        return this.d;
    }

    private u(Context context) {
        this.e = -1L;
        this.f = -1;
        this.g = -1;
        this.b = new w(context);
        Cursor rawQuery = this.b.getReadableDatabase().rawQuery("SELECT APKVERSION,_id,DOWNLOADSTATUS,DOWNLOADFLAGS FROM MetadataColumns LIMIT 1", null);
        if (rawQuery != null && rawQuery.moveToFirst()) {
            this.f = rawQuery.getInt(0);
            this.e = rawQuery.getLong(1);
            this.g = rawQuery.getInt(2);
            this.h = rawQuery.getInt(3);
            rawQuery.close();
        }
        i = this;
    }

    protected h a(String str) {
        Cursor cursor = null;
        try {
            Cursor query = this.b.getReadableDatabase().query("DownloadColumns", j, "FN = ?", new String[]{str}, null, null, null);
            if (query != null) {
                try {
                    if (query.moveToFirst()) {
                        h a2 = a(query);
                        if (query == null) {
                            return a2;
                        }
                        query.close();
                        return a2;
                    }
                } catch (Throwable th) {
                    th = th;
                    cursor = query;
                    if (cursor != null) {
                        cursor.close();
                    }
                    throw th;
                }
            }
            if (query != null) {
                query.close();
            }
            return null;
        } catch (Throwable th2) {
            th = th2;
        }
    }

    public long a(h hVar) {
        return a(hVar.b);
    }

    public long a(int i2) {
        SQLiteStatement b = b();
        b.clearBindings();
        b.bindLong(1, i2);
        try {
            return b.simpleQueryForLong();
        } catch (SQLiteDoneException e) {
            return -1L;
        }
    }

    public void b(h hVar) {
        SQLiteStatement c = c();
        c.clearBindings();
        c.bindLong(1, hVar.f);
        c.bindLong(2, hVar.b);
        c.execute();
    }

    public boolean c(h hVar) {
        ContentValues contentValues = new ContentValues();
        contentValues.put("FILEIDX", Integer.valueOf(hVar.b));
        contentValues.put("FN", hVar.c);
        contentValues.put("URI", hVar.a);
        contentValues.put("ETAG", hVar.d);
        contentValues.put("TOTALBYTES", Long.valueOf(hVar.e));
        contentValues.put("CURRENTBYTES", Long.valueOf(hVar.f));
        contentValues.put("LASTMOD", Long.valueOf(hVar.g));
        contentValues.put("STATUS", Integer.valueOf(hVar.h));
        contentValues.put("CONTROL", Integer.valueOf(hVar.i));
        contentValues.put("FAILCOUNT", Integer.valueOf(hVar.j));
        contentValues.put("RETRYAFTER", Integer.valueOf(hVar.k));
        contentValues.put("REDIRECTCOUNT", Integer.valueOf(hVar.l));
        return a(hVar, contentValues);
    }

    public boolean a(h hVar, ContentValues contentValues) {
        long a2 = hVar == null ? -1L : a(hVar);
        try {
            SQLiteDatabase writableDatabase = this.b.getWritableDatabase();
            if (a2 == -1) {
                return -1 != writableDatabase.insert("DownloadColumns", "URI", contentValues);
            }
            if (1 != writableDatabase.update("DownloadColumns", contentValues, "DownloadColumns._id = " + a2, null)) {
            }
            return false;
        } catch (SQLiteException e) {
            e.printStackTrace();
            return false;
        }
    }

    public boolean b(int i2) {
        if (this.h == i2) {
            return true;
        }
        ContentValues contentValues = new ContentValues();
        contentValues.put("DOWNLOADFLAGS", Integer.valueOf(i2));
        if (a(contentValues)) {
            this.h = i2;
            return true;
        }
        return false;
    }

    public boolean c(int i2) {
        if (this.g == i2) {
            return true;
        }
        ContentValues contentValues = new ContentValues();
        contentValues.put("DOWNLOADSTATUS", Integer.valueOf(i2));
        if (a(contentValues)) {
            this.g = i2;
            return true;
        }
        return false;
    }

    public boolean a(ContentValues contentValues) {
        SQLiteDatabase writableDatabase = this.b.getWritableDatabase();
        if (-1 == this.e) {
            long insert = writableDatabase.insert("MetadataColumns", "APKVERSION", contentValues);
            if (-1 == insert) {
                return false;
            }
            this.e = insert;
        } else if (writableDatabase.update("MetadataColumns", contentValues, "_id = " + this.e, null) == 0) {
            return false;
        }
        return true;
    }

    public boolean a(int i2, int i3) {
        ContentValues contentValues = new ContentValues();
        contentValues.put("APKVERSION", Integer.valueOf(i2));
        contentValues.put("DOWNLOADSTATUS", Integer.valueOf(i3));
        if (!a(contentValues)) {
            return false;
        }
        this.f = i2;
        this.g = i3;
        return true;
    }

    public boolean d(h hVar) {
        Cursor cursor;
        try {
            cursor = this.b.getReadableDatabase().query("DownloadColumns", j, "FN= ?", new String[]{hVar.c}, null, null, null);
            if (cursor != null) {
                try {
                    if (cursor.moveToFirst()) {
                        a(hVar, cursor);
                        if (cursor != null) {
                            cursor.close();
                        }
                        return true;
                    }
                } catch (Throwable th) {
                    th = th;
                    if (cursor != null) {
                        cursor.close();
                    }
                    throw th;
                }
            }
            if (cursor != null) {
                cursor.close();
            }
            return false;
        } catch (Throwable th2) {
            th = th2;
            cursor = null;
        }
    }

    public void a(h hVar, Cursor cursor) {
        hVar.a = cursor.getString(1);
        hVar.d = cursor.getString(2);
        hVar.e = cursor.getLong(3);
        hVar.f = cursor.getLong(4);
        hVar.g = cursor.getLong(5);
        hVar.h = cursor.getInt(6);
        hVar.i = cursor.getInt(7);
        hVar.j = cursor.getInt(8);
        hVar.k = cursor.getInt(9);
        hVar.l = cursor.getInt(10);
    }

    public h a(Cursor cursor) {
        h hVar = new h(cursor.getInt(11), cursor.getString(0), getClass().getPackage().getName());
        a(hVar, cursor);
        return hVar;
    }

    public h[] a() {
        Cursor cursor = null;
        try {
            Cursor query = this.b.getReadableDatabase().query("DownloadColumns", j, null, null, null, null, null);
            if (query != null) {
                try {
                    if (query.moveToFirst()) {
                        h[] hVarArr = new h[query.getCount()];
                        int i2 = 0;
                        while (true) {
                            int i3 = i2 + 1;
                            hVarArr[i2] = a(query);
                            if (!query.moveToNext()) {
                                break;
                            }
                            i2 = i3;
                        }
                        if (query == null) {
                            return hVarArr;
                        }
                        query.close();
                        return hVarArr;
                    }
                } catch (Throwable th) {
                    th = th;
                    cursor = query;
                    if (cursor != null) {
                        cursor.close();
                    }
                    throw th;
                }
            }
            if (query != null) {
                query.close();
            }
            return null;
        } catch (Throwable th2) {
            th = th2;
        }
    }
}
