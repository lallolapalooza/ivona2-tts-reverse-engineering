package com.ivona.tts.voicelib;

/* compiled from: VoiceFiles.java */
/* loaded from: classes.dex */
class q {
    private static final q[] d = {new q("cym.gbr.gwyneth", "vox_cy_gwyneth22v", "lang_cy.dat"), new q("deu.deu.marlene", "vox_de_marlene22v", "lang_de.dat"), new q("eng.aus.nicole", "vox_en_au_nicole22v", "lang_en_au.dat"), new q("eng.gbr.amy", "vox_en_gb_amy22v", "lang_en_gb.dat"), new q("eng.usa.kendra", "vox_en_us_kendra22v", "lang_en_us.dat"), new q("eng.gbr.gwyneth", "vox_en_wls_gwyneth22v", "lang_en_gb_wls.dat"), new q("spa.esp.conchita", "vox_es_conchita22v", "lang_es.dat"), new q("spa.usa.penelope", "vox_es_us_penelope22v", "lang_es_us.dat"), new q("fra.fra.celine", "vox_fr_celine22v", "lang_fr_fr.dat"), new q("isl.isl.dora", "vox_is_dora22v", "lang_is.dat"), new q("ita.ita.giorgio", "vox_it_giorgio22v", "lang_it.dat"), new q("pol.pol.maja", "vox_pl_maja22v", "lang_pl.dat"), new q("por.bra.vitoria", "vox_pt_br_vitoria22v", "lang_pt_br.dat"), new q("ron.rou.carmen", "vox_ro_carmen22v", "lang_ro.dat")};
    private final String a;
    private final String b;
    private final String c;

    public String a() {
        return this.b;
    }

    public String b() {
        return this.c;
    }

    public q(String str, String str2, String str3) {
        this.a = str;
        this.b = str2;
        this.c = str3;
    }

    public static q a(String str) {
        for (q qVar : d) {
            if (qVar.a.equals(str)) {
                return qVar;
            }
        }
        return null;
    }
}
