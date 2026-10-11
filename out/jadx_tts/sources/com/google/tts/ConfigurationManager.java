package com.google.tts;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.net.URLConnection;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/* loaded from: classes.dex */
public class ConfigurationManager extends Activity {
    @Override // android.app.Activity
    public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        if (!a()) {
            setContentView(R.layout.main);
            new Thread(new dataDownloader()).start();
        } else {
            startActivityForResult(new Intent(this, (Class<?>) TextToSpeechSettings.class), 42);
            finish();
        }
    }

    public class dataDownloader implements Runnable {
        public dataDownloader() {
        }

        @Override // java.lang.Runnable
        public void run() {
            ConfigurationManager.b();
            ConfigurationManager.this.finish();
        }
    }

    public static boolean a() {
        String[] strArr = {"af_dict", "config", "cs_dict", "cy_dict", "de_dict", "el_dict", "en_dict", "eo_dict", "es_dict", "fi_dict", "fr_dict", "grc_dict", "hbs_dict", "hi_dict", "hu_dict", "id_dict", "is_dict", "it_dict", "jbo_dict", "ku_dict", "la_dict", "mk_dict", "nl_dict", "no_dict", "phondata", "phonindex", "phontab", "pl_dict", "pt_dict", "ro_dict", "ru_dict", "sk_dict", "sv_dict", "sw_dict", "ta_dict", "tr_dict", "vi_dict", "zh_dict", "zhy_dict", "mbrola/dummyfile", "mbrola_ph/af1_phtrans", "mbrola_ph/ca1_phtrans", "mbrola_ph/cr1_phtrans", "mbrola_ph/cs_phtrans", "mbrola_ph/de2_phtrans", "mbrola_ph/de4_phtrans", "mbrola_ph/de6_phtrans", "mbrola_ph/en1_phtrans", "mbrola_ph/es_phtrans", "mbrola_ph/es4_phtrans", "mbrola_ph/fr1_phtrans", "mbrola_ph/gr2_phtrans", "mbrola_ph/grc-de6_phtrans", "mbrola_ph/hu1_phtrans", "mbrola_ph/id1_phtrans", "mbrola_ph/in1_phtrans", "mbrola_ph/it3_phtrans", "mbrola_ph/la1_phtrans", "mbrola_ph/nl_phtrans", "mbrola_ph/pl1_phtrans", "mbrola_ph/pt_phtrans", "mbrola_ph/ptbr_phtrans", "mbrola_ph/ptbr4_phtrans", "mbrola_ph/ro1_phtrans", "mbrola_ph/sv_phtrans", "mbrola_ph/sv2_phtrans", "mbrola_ph/us_phtrans", "mbrola_ph/us3_phtrans", "soundicons/dummyfile", "voices/af", "voices/bs", "voices/cs", "voices/cy", "voices/de", "voices/default", "voices/el", "voices/eo", "voices/es", "voices/es-la", "voices/fi", "voices/fr", "voices/fr-be", "voices/grc", "voices/hi", "voices/hr", "voices/hu", "voices/id", "voices/is", "voices/it", "voices/jbo", "voices/ku", "voices/la", "voices/mk", "voices/nl", "voices/no", "voices/pl", "voices/pt", "voices/pt-pt", "voices/ro", "voices/ru", "voices/sk", "voices/sr", "voices/sv", "voices/sw", "voices/ta", "voices/tr", "voices/vi", "voices/zh", "voices/zhy", "voices/!v/croak", "voices/!v/f1", "voices/!v/f2", "voices/!v/f3", "voices/!v/f4", "voices/!v/m1", "voices/!v/m2", "voices/!v/m3", "voices/!v/m4", "voices/!v/m5", "voices/!v/m6", "voices/!v/whisper", "voices/en/en", "voices/en/en-n", "voices/en/en-r", "voices/en/en-rp", "voices/en/en-sc", "voices/en/en-wi", "voices/en/en-wm", "voices/mb/mb-af1", "voices/mb/mb-af1-en", "voices/mb/mb-br1", "voices/mb/mb-br3", "voices/mb/mb-br4", "voices/mb/mb-cr1", "voices/mb/mb-cz2", "voices/mb/mb-de2", "voices/mb/mb-de4", "voices/mb/mb-de4-en", "voices/mb/mb-de5", "voices/mb/mb-de5-en", "voices/mb/mb-de6", "voices/mb/mb-de6-grc", "voices/mb/mb-de7", "voices/mb/mb-en1", "voices/mb/mb-es1", "voices/mb/mb-es2", "voices/mb/mb-fr1", "voices/mb/mb-fr1-en", "voices/mb/mb-fr4", "voices/mb/mb-fr4-en", "voices/mb/mb-gr2", "voices/mb/mb-gr2-en", "voices/mb/mb-hu1", "voices/mb/mb-hu1-en", "voices/mb/mb-id1", "voices/mb/mb-it3", "voices/mb/mb-it4", "voices/mb/mb-la1", "voices/mb/mb-nl2", "voices/mb/mb-nl2-en", "voices/mb/mb-pl1", "voices/mb/mb-pl1-en", "voices/mb/mb-ro1", "voices/mb/mb-ro1-en", "voices/mb/mb-sw1", "voices/mb/mb-sw1-en", "voices/mb/mb-sw2", "voices/mb/mb-sw2-en", "voices/mb/mb-us1", "voices/mb/mb-us2", "voices/mb/mb-us3"};
        if (!new File("/sdcard/espeak-data/").isDirectory()) {
            return false;
        }
        for (String str : strArr) {
            if (!new File(String.valueOf("/sdcard/espeak-data/") + str).exists()) {
                for (String str2 : strArr) {
                    new File(String.valueOf("/sdcard/espeak-data/") + str2).delete();
                }
                return false;
            }
        }
        return true;
    }

    public static void b() {
        try {
            if (new File("/sdcard/").canWrite()) {
                File file = new File("/sdcard/espeak-data/");
                file.mkdir();
                URLConnection openConnection = new URL(new URL(new URL("http://eyes-free.googlecode.com/svn/trunk/thirdparty/espeak-data.zip"), "http://eyes-free.googlecode.com/svn/trunk/thirdparty/espeak-data.zip").toString()).openConnection();
                openConnection.connect();
                InputStream inputStream = openConnection.getInputStream();
                File file2 = new File("/sdcard/espeak-data/data.zip");
                file2.createNewFile();
                FileOutputStream fileOutputStream = new FileOutputStream(file2);
                byte[] bArr = new byte[16384];
                while (true) {
                    int read = inputStream.read(bArr);
                    if (read <= 0) {
                        break;
                    } else {
                        fileOutputStream.write(bArr, 0, read);
                    }
                }
                inputStream.close();
                fileOutputStream.close();
                ZipFile zipFile = new ZipFile("/sdcard/espeak-data/data.zip");
                Enumeration<? extends ZipEntry> entries = zipFile.entries();
                while (entries.hasMoreElements()) {
                    ZipEntry nextElement = entries.nextElement();
                    if (nextElement.isDirectory()) {
                        new File(file + nextElement.getName()).mkdir();
                    } else {
                        InputStream inputStream2 = zipFile.getInputStream(nextElement);
                        String canonicalPath = new File("/sdcard/espeak-data/" + nextElement.getName()).getCanonicalPath();
                        String substring = canonicalPath.substring(canonicalPath.lastIndexOf("/") + 1);
                        String substring2 = canonicalPath.substring(0, canonicalPath.lastIndexOf("/"));
                        new File(substring2).mkdirs();
                        File file3 = new File(substring2, substring);
                        file3.createNewFile();
                        FileOutputStream fileOutputStream2 = new FileOutputStream(file3);
                        byte[] bArr2 = new byte[16384];
                        while (true) {
                            int read2 = inputStream2.read(bArr2);
                            if (read2 <= 0) {
                                break;
                            } else {
                                fileOutputStream2.write(bArr2, 0, read2);
                            }
                        }
                        inputStream2.close();
                        fileOutputStream2.close();
                    }
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
