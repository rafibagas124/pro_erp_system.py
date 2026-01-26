import streamlit as st
import pandas as pd
import sqlite3
import qrcode
import base64
from fpdf import FPDF
from io import BytesIO
from PIL import Image
from datetime import datetime
import matplotlib.pyplot as plt

# --- 1. CONFIG & STYLING (MODERN UI) ---
st.set_page_config(page_title="Pro ERP System", page_icon="🚀", layout="wide")

# CSS Custom biar tampilan lebih Mahal
st.markdown("""
    <style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; border-left: 5px solid #ff4b4b;}
    .stButton>button {width: 100%; border-radius: 5px;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEM DATABASE CANGGIH (IMAGE SUPPORT) ---
def init_db():
    conn = sqlite3.connect('master_business.db')
    c = conn.cursor()
    # Tabel Keuangan
    c.execute('''CREATE TABLE IF NOT EXISTS keuangan 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tanggal TEXT, tipe TEXT, 
                 kategori TEXT, nominal REAL, keterangan TEXT, bukti_img TEXT)''')
    # Tabel Stok
    c.execute('''CREATE TABLE IF NOT EXISTS stok 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kode TEXT, nama TEXT, 
                 jumlah INTEGER, harga_beli REAL, harga_jual REAL, foto_img TEXT, min_stok INTEGER)''')
    # Tabel Kontak
    c.execute('''CREATE TABLE IF NOT EXISTS kontak 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nama TEXT, role TEXT, 
                 hp TEXT, alamat TEXT, is_prioritas INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. HELPER FUNCTIONS (OTAK APLIKASI) ---
# Fungsi Kompresi Foto ke Text (Base64) biar Database gak berat
def process_image(image_file):
    if image_file is not None:
        img = Image.open(image_file)
        # Resize gambar biar enteng (Max 800px)
        img.thumbnail((800, 800))
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=70) # Kompres kualitas 70%
        return base64.b64encode(buffered.getvalue()).decode()
    return None

def run_query(query, params=()):
    conn = sqlite3.connect('master_business.db')
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def run_command(query, params=()):
    conn = sqlite3.connect('master_business.db')
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

# Format Rupiah
def format_idr(val):
    return f"Rp {val:,.0f}"

# --- 4. NAVIGASI SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.title("Admin Pro v2.0")
    
    # Bahasa
    lang = st.selectbox("🌍 Bahasa / Language", ["Indonesia", "English"])
    
    menu = st.radio("Menu Navigasi", 
        ["Dashboard", "Keuangan", "Inventory & Stok", "CRM (Pelanggan)", "Invoice Maker", "Settings & Backup"])

# --- 5. LOGIKA MENU PRO ---

# === MENU 1: DASHBOARD ANALYTICS ===
if menu == "Dashboard":
    st.title("📊 Executive Dashboard")
    
    # Ambil Data Realtime
    df_uang = run_query("SELECT * FROM keuangan")
    df_stok = run_query("SELECT * FROM stok")
    
    # Hitung Saldo
    pemasukan = df_uang[df_uang['tipe'] == 'Pemasukan']['nominal'].sum()
    pengeluaran = df_uang[df_uang['tipe'] == 'Pengeluaran']['nominal'].sum()
    saldo = pemasukan - pengeluaran
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Saldo Bersih", format_idr(saldo), delta="Cash Flow")
    col2.metric("📦 Total Item Stok", f"{df_stok['jumlah'].sum()} Unit")
    col3.metric("📉 Pengeluaran", format_idr(pengeluaran), delta_color="inverse")
    
    # Notifikasi Stok Menipis (Alert System)
    if not df_stok.empty:
        low_stock = df_stok[df_stok['jumlah'] <= df_stok['min_stok']]
        col4.metric("⚠️ Stok Kritis", f"{len(low_stock)} Item", delta_color="inverse")
        if not low_stock.empty:
            st.warning(f"PERINGATAN: {len(low_stock)} barang stoknya menipis! Cek Inventory.")
    
    # Grafik Keuangan
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Tren Arus Kas")
        if not df_uang.empty:
            df_uang['tanggal'] = pd.to_datetime(df_uang['tanggal'])
            daily = df_uang.groupby(['tanggal', 'tipe'])['nominal'].sum().unstack().fillna(0)
            st.bar_chart(daily)
        else:
            st.info("Belum ada data transaksi.")
            
    with c2:
        st.subheader("Aset Stok Termahal")
        if not df_stok.empty:
            top_stok = df_stok.sort_values(by='harga_beli', ascending=False).head(5)
            st.bar_chart(top_stok.set_index('nama')['harga_beli'])

# === MENU 2: KEUANGAN (DENGAN BUKTI FOTO) ===
elif menu == "Keuangan":
    st.header("💵 Jurnal Keuangan")
    
    tab1, tab2 = st.tabs(["➕ Input Transaksi", "📜 Data & Laporan"])
    
    with tab1:
        with st.form("form_keuangan", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                tgl = st.date_input("Tanggal Transaksi")
                tipe = st.selectbox("Jenis", ["Pemasukan", "Pengeluaran"])
                kategori = st.selectbox("Kategori", ["Penjualan", "Gaji", "Operasional", "Bahan Baku", "Lainnya"])
            with col_b:
                nom = st.number_input("Nominal (Rp)", min_value=0.0, step=1000.0)
                ket = st.text_area("Keterangan Detail")
                bukti = st.file_uploader("Upload Bukti/Struk (Otomatis Disimpan ke DB)", type=['jpg','png','jpeg'])
            
            if st.form_submit_button("Simpan Transaksi"):
                img_str = process_image(bukti) # Convert ke Base64
                run_command("INSERT INTO keuangan (tanggal, tipe, kategori, nominal, keterangan, bukti_img) VALUES (?,?,?,?,?,?)", 
                            (tgl, tipe, kategori, nom, ket, img_str))
                st.success("Transaksi Berhasil Disimpan!")

    with tab2:
        # Filter Data
        filter_tipe = st.multiselect("Filter Tipe", ["Pemasukan", "Pengeluaran"], default=["Pemasukan", "Pengeluaran"])
        df = run_query(f"SELECT * FROM keuangan WHERE tipe IN ({','.join(['?']*len(filter_tipe))})", filter_tipe)
        
        # Tampilan Data yang bisa di-expand
        for i, row in df.iterrows():
            with st.expander(f"{row['tanggal']} | {row['tipe']} | {format_idr(row['nominal'])}"):
                c_img, c_det = st.columns([1,3])
                with c_img:
                    if row['bukti_img']:
                        # Decode Base64 jadi Gambar lagi
                        img_bytes = base64.b64decode(row['bukti_img'])
                        st.image(BytesIO(img_bytes), caption="Bukti Foto", width=150)
                    else:
                        st.write("🚫 Tidak ada bukti")
                with c_det:
                    st.write(f"**Kategori:** {row['kategori']}")
                    st.write(f"**Ket:** {row['keterangan']}")
                    if st.button("Hapus Data", key=f"del_{row['id']}"):
                        run_command("DELETE FROM keuangan WHERE id=?", (row['id'],))
                        st.experimental_rerun()

# === MENU 3: INVENTORY (EDITABLE GRID) ===
elif menu == "Inventory & Stok":
    st.header("📦 Manajemen Gudang")
    
    # Input Barang Baru
    with st.expander("➕ Tambah Barang Baru"):
        with st.form("new_item"):
            c1, c2, c3 = st.columns(3)
            kode = c1.text_input("Kode Barang/SKU")
            nama = c2.text_input("Nama Barang")
            jum = c3.number_input("Stok Awal", 0)
            
            c4, c5, c6 = st.columns(3)
            hb = c4.number_input("Harga Beli", 0)
            hj = c5.number_input("Harga Jual", 0)
            min_s = c6.number_input("Alert Jika Stok <", 5)
            
            foto = st.file_uploader("Foto Produk")
            
            if st.form_submit_button("Tambah Stok"):
                foto_str = process_image(foto)
                run_command("INSERT INTO stok (kode, nama, jumlah, harga_beli, harga_jual, foto_img, min_stok) VALUES (?,?,?,?,?,?,?)",
                            (kode, nama, jum, hb, hj, foto_str, min_s))
                st.success("Barang masuk gudang!")

    # Tabel Edit Langsung (Pro Feature)
    st.subheader("Daftar Barang (Edit Langsung di Tabel)")
    df_stok = run_query("SELECT id, kode, nama, jumlah, harga_beli, harga_jual, min_stok FROM stok")
    
    # Fitur Data Editor (Bisa edit angka stok langsung di tabel)
    edited_df = st.data_editor(df_stok, num_rows="dynamic", key="editor_stok")
    
    if st.button("💾 Simpan Perubahan Edit"):
        # Logika update data (Sederhana: Loop update)
        # Note: Untuk produksi skala besar, logic ini perlu dioptimalkan
        for index, row in edited_df.iterrows():
            run_command("UPDATE stok SET jumlah=?, harga_jual=? WHERE id=?", (row['jumlah'], row['harga_jual'], row['id']))
        st.success("Database Stok Diperbarui!")

    # Galeri & QR Generator
    st.subheader("Galeri & QR Code")
    items = run_query("SELECT * FROM stok")
    if not items.empty:
        grid = st.columns(4)
        for i, row in items.iterrows():
            with grid[i % 4]:
                st.markdown(f"**{row['nama']}**")
                if row['foto_img']:
                    ib = base64.b64decode(row['foto_img'])
                    st.image(BytesIO(ib), use_container_width=True)
                
                # Generate QR
                qr_btn = st.button(f"QR: {row['kode']}", key=f"qr_{row['id']}")
                if qr_btn:
                    qr = qrcode.make(f"ID:{row['kode']}|{row['nama']}|Rp{row['harga_jual']}")
                    buf = BytesIO()
                    qr.save(buf)
                    st.image(buf.getvalue(), caption="Scan Me")

# === MENU 4: CRM (KONTAK PELANGGAN) ===
elif menu == "CRM (Pelanggan)":
    st.header("👥 Customer Relationship Management")
    
    c1, c2 = st.columns([1,2])
    with c1:
        st.subheader("Input Kontak")
        nama = st.text_input("Nama Lengkap")
        role = st.selectbox("Tipe", ["Customer", "Supplier", "Karyawan"])
        hp = st.text_input("WhatsApp")
        alamat = st.text_area("Alamat")
        prio = st.checkbox("🔥 Prioritas Tinggi (VIP)")
        
        if st.button("Simpan Kontak"):
            run_command("INSERT INTO kontak (nama, role, hp, alamat, is_prioritas) VALUES (?,?,?,?,?)",
                        (nama, role, hp, alamat, 1 if prio else 0))
            st.success("Tersimpan")

    with c2:
        st.subheader("Buku Telepon")
        # Urutkan VIP paling atas
        df_k = run_query("SELECT * FROM kontak ORDER BY is_prioritas DESC, nama ASC")
        
        for i, r in df_k.iterrows():
            icon = "👑 VIP" if r['is_prioritas'] == 1 else "👤"
            with st.expander(f"{icon} {r['nama']} ({r['role']})"):
                st.write(f"📞 {r['hp']}")
                st.write(f"🏠 {r['alamat']}")
                st.write(f"https://wa.me/{r['hp'].replace('08','628').replace(' ','')}")

# === MENU 5: INVOICE MAKER (PDF) ===
elif menu == "Invoice Maker":
    st.header("🖨️ Buat Invoice Profesional")
    
    col_cust, col_item = st.columns(2)
    
    with col_cust:
        # Ambil list customer dari DB
        cust_data = run_query("SELECT nama FROM kontak WHERE role='Customer'")
        cust_list = cust_data['nama'].tolist() if not cust_data.empty else []
        pembeli = st.selectbox("Pilih Customer", cust_list)
        tgl_inv = st.date_input("Tanggal Invoice")
    
    with col_item:
        # Ambil list barang
        stok_data = run_query("SELECT nama, harga_jual FROM stok")
        stok_dict = dict(zip(stok_data['nama'], stok_data['harga_jual'])) if not stok_data.empty else {}
        items_beli = st.multiselect("Pilih Barang", options=list(stok_dict.keys()))
    
    # Tabel Keranjang Belanja
    keranjang = []
    total_bayar = 0
    if items_beli:
        st.subheader("Rincian Belanja")
        for item in items_beli:
            cols = st.columns(3)
            qty = cols[1].number_input(f"Qty {item}", 1, key=f"q_{item}")
            harga = stok_dict[item]
            subtotal = qty * harga
            total_bayar += subtotal
            cols[0].write(f"**{item}** (@ {format_idr(harga)})")
            cols[2].write(f"= {format_idr(subtotal)}")
            keranjang.append({"item": item, "qty": qty, "harga": harga, "subtotal": subtotal})
            
        st.success(f"TOTAL TAGIHAN: {format_idr(total_bayar)}")
        
        if st.button("🖨️ DOWNLOAD PDF INVOICE"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt="INVOICE / NOTA", ln=1, align="C")
            
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Customer: {pembeli}", ln=1)
            pdf.cell(200, 10, txt=f"Tanggal: {tgl_inv}", ln=1)
            pdf.line(10, 30, 200, 30)
            
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(80, 10, "Barang", 1)
            pdf.cell(30, 10, "Qty", 1)
            pdf.cell(40, 10, "Harga", 1)
            pdf.cell(40, 10, "Subtotal", 1)
            pdf.ln()
            
            pdf.set_font("Arial", size=12)
            for k in keranjang:
                pdf.cell(80, 10, k['item'], 1)
                pdf.cell(30, 10, str(k['qty']), 1)
                pdf.cell(40, 10, str(k['harga']), 1)
                pdf.cell(40, 10, str(k['subtotal']), 1)
                pdf.ln()
            
            pdf.cell(150, 10, "TOTAL TOTAL", 1)
            pdf.cell(40, 10, str(total_bayar), 1)
            
            # Output
            pdf_out = pdf.output(dest='S').encode('latin-1')
            st.download_button("Klik untuk Simpan PDF", pdf_out, f"INV_{pembeli}_{datetime.now().strftime('%H%M')}.pdf")

# === MENU 6: SETTINGS & BACKUP ===
elif menu == "Settings & Backup":
    st.header("⚙️ Pengaturan & Backup")
    st.info("PENTING: Download database secara rutin agar data aman.")
    
    with open("master_business.db", "rb") as fp:
        st.download_button(
            label="💾 DOWNLOAD FULL BACKUP (DATABASE + FOTO)",
            data=fp,
            file_name=f"Backup_Toko_{datetime.now().strftime('%Y%m%d')}.db",
            mime="application/octet-stream",
            help="File ini berisi semua data keuangan, stok, kontak, DAN FOTO."
        )
    
    st.divider()
    st.warning("Zona Bahaya")
    if st.button("⚠️ Reset/Hapus Semua Data"):
        st.error("Fitur ini dimatikan demi keamanan.")

# FOOTER
st.markdown("---")
st.markdown("<div style='text-align: center'>System ERP V2.0 Pro | Powered by Python Streamlit</div>", unsafe_allow_html=True)