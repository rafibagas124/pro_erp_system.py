import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder
from fpdf import FPDF
import qrcode
from io import BytesIO
from datetime import datetime
import os

# --- 1. KONFIGURASI HALAMAN & CSS CUSTOM ---
st.set_page_config(page_title="Super ERP System", layout="wide", page_icon="📊")

# Custom CSS untuk Font Times New Roman (Sesuai request)
st.markdown("""
    <style>
    html, body, [class*="css"]  {
        font-family: 'Times New Roman', serif; 
    }
    .stApp {
        background-image: linear-gradient(to right top, #ffffff, #f0f2f6);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNGSI UTILITAS (BACKEND SEDERHANA) ---

# Simulasi Database (Menggunakan CSV agar ringan & portable)
DATA_FILE = 'data/transaksi.csv'
if not os.path.exists('data'):
    os.makedirs('data')

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=['Tanggal', 'Kategori', 'Keterangan', 'Masuk', 'Keluar', 'Pelanggan', 'Status'])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# Multi-bahasa
lang_dict = {
    "ID": {"title": "Sistem Manajemen Keuangan & Stok", "menu": "Navigasi", "add": "Tambah Data", "save": "Simpan"},
    "EN": {"title": "Financial & Stock Management System", "menu": "Navigation", "add": "Add Data", "save": "Save"}
}

# --- 3. SIDEBAR & NAVIGASI ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
    bahasa = st.selectbox("Bahasa / Language", ["ID", "EN"])
    txt = lang_dict[bahasa]
    
    st.header(txt["menu"])
    menu = st.radio("Pilih Fitur:", 
        ["Dashboard & Grafik", "Input Transaksi (Excel Style)", "Invoice & Print", "File Manager & QR", "Kontak & Prioritas"])

    st.info("💡 Tips: Aplikasi ini menyimpan data secara otomatis.")

# --- 4. FITUR UTAMA ---

df = load_data()

# A. DASHBOARD & GRAFIK (Analisa)
if menu == "Dashboard & Grafik":
    st.title(f"📊 {txt['title']}")
    
    # Ringkasan (Sum)
    total_masuk = df['Masuk'].sum()
    total_keluar = df['Keluar'].sum()
    selisih = total_masuk - total_keluar
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pemasukan", f"Rp {total_masuk:,.0f}")
    col2.metric("Total Pengeluaran", f"Rp {total_keluar:,.0f}")
    col3.metric("Sisa Saldo / Profit", f"Rp {selisih:,.0f}", delta_color="normal")

    # Grafik (Otomatis muncul sesuai data)
    st.subheader("Analisa Grafik")
    if not df.empty:
        tab1, tab2 = st.tabs(["Grafik Batang", "Grafik Lingkaran"])
        
        with tab1:
            st.caption("Tren Transaksi Harian")
            chart_data = df.groupby('Tanggal')[['Masuk', 'Keluar']].sum().reset_index()
            st.bar_chart(chart_data, x='Tanggal', y=['Masuk', 'Keluar'])
            
        with tab2:
            st.caption("Proporsi Pengeluaran vs Pemasukan")
            pie_df = pd.DataFrame({'Tipe': ['Masuk', 'Keluar'], 'Nilai': [total_masuk, total_keluar]})
            fig = px.pie(pie_df, values='Nilai', names='Tipe', title='Rasio Keuangan')
            st.plotly_chart(fig)
    else:
        st.warning("Belum ada data untuk ditampilkan.")

# B. INPUT TRANSAKSI (Gaya Spreadsheet/Excel)
elif menu == "Input Transaksi (Excel Style)":
    st.title("📝 Input Data & Stok")
    st.markdown("Anda bisa mengedit tabel di bawah ini layaknya **Excel** (Klik 2x pada sel).")

    # Konfigurasi Tabel Interaktif (AgGrid)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_default_column(editable=True, groupable=True)
    gb.configure_column("Tanggal", type=["dateColumnFilter","customDateTimeFormat"], custom_format_string='yyyy-MM-dd')
    gb.configure_column("Masuk", type=["numericColumn","numberColumnFilter","customNumericFormat"], precision=0)
    gb.configure_column("Keluar", type=["numericColumn","numberColumnFilter","customNumericFormat"], precision=0)
    gridOptions = gb.build()

    grid_response = AgGrid(
        df, 
        gridOptions=gridOptions,
        enable_enterprise_modules=False,
        height=400, 
        width='100%',
        theme='streamlit' # Pilihan tema tabel
    )

    # Tombol Simpan Perubahan
    if st.button("💾 Simpan Perubahan ke Database"):
        new_df = pd.DataFrame(grid_response['data'])
        save_data(new_df)
        st.success("Data berhasil diperbarui!")

    # Form Input Manual Cepat
    with st.expander("➕ Tambah Data Manual (Formulir)"):
        with st.form("entry_form"):
            c1, c2 = st.columns(2)
            tgl = c1.date_input("Tanggal")
            kategori = c2.selectbox("Kategori", ["Penjualan", "Pembelian Stok", "Operasional", "Gaji"])
            ket = st.text_input("Keterangan Item")
            masuk = c1.number_input("Pemasukan (Rp)", min_value=0)
            keluar = c2.number_input("Pengeluaran (Rp)", min_value=0)
            pelanggan = st.text_input("Nama Pelanggan/Suplier")
            
            submitted = st.form_submit_button("Submit Data")
            if submitted:
                new_data = pd.DataFrame([{
                    'Tanggal': tgl, 'Kategori': kategori, 'Keterangan': ket,
                    'Masuk': masuk, 'Keluar': keluar, 'Pelanggan': pelanggan, 'Status': 'Baru'
                }])
                df = pd.concat([df, new_data], ignore_index=True)
                save_data(df)
                st.rerun() # Refresh halaman

# C. INVOICE & PRINT
elif menu == "Invoice & Print":
    st.title("🖨️ Cetak Invoice / Laporan")
    
    # Pilih Data
    pilihan = st.selectbox("Pilih Transaksi untuk Invoice:", df['Keterangan'].unique())
    data_inv = df[df['Keterangan'] == pilihan].iloc[0] if not df.empty else None
    
    if data_inv is not None:
        st.write("Preview Data:", data_inv)
        
        if st.button("Generate Invoice (PDF)"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="INVOICE TAGIHAN", ln=1, align='C')
            pdf.cell(200, 10, txt=f"Tanggal: {data_inv['Tanggal']}", ln=2, align='L')
            pdf.cell(200, 10, txt=f"Item: {data_inv['Keterangan']}", ln=3, align='L')
            pdf.cell(200, 10, txt=f"Total Tagihan: Rp {data_inv['Masuk'] if data_inv['Masuk'] > 0 else data_inv['Keluar']}", ln=4, align='L')
            
            # Simpan ke memory buffer agar bisa didownload
            html = pdf.output(dest='S').encode('latin-1')
            st.download_button(label="Download PDF", data=html, file_name=f"Invoice_{pilihan}.pdf", mime='application/pdf')

    st.markdown("---")
    # Download Seluruh Data (Backup)
    st.subheader("Backup Data")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Laporan Excel/CSV", data=csv, file_name="laporan_keuangan.csv")

# D. FILE MANAGER & QR CODE
elif menu == "File Manager & QR":
    st.title("📂 File & QR Generator")
    
    # 1. Upload File
    uploaded_file = st.file_uploader("Upload Bukti / Foto / Video", type=['png', 'jpg', 'pdf', 'mp4'])
    if uploaded_file is not None:
        st.success(f"File {uploaded_file.name} berhasil di-upload sementara!")
        # Di sini bisa ditambahkan logika simpan ke folder
        
    st.markdown("---")
    
    # 2. QR Code Generator
    st.subheader("Buat QR Code Sendiri")
    link_data = st.text_input("Masukan Link / Teks untuk dijadikan QR Code:")
    nama_qr = st.text_input("Label QR Code:")
    
    if link_data and st.button("Generate QR"):
        qr = qrcode.make(link_data)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()
        
        st.image(img_bytes, caption=f"QR Code: {nama_qr}", width=200)
        st.download_button("Download QR Image", data=img_bytes, file_name=f"QR_{nama_qr}.png", mime="image/png")

# E. KONTAK & PRIORITAS
elif menu == "Kontak & Prioritas":
    st.title("☎️ Manajemen Kontak")
    
    # Simple form kontak
    c1, c2, c3 = st.columns([2, 2, 1])
    nama = c1.text_input("Nama Kontak")
    telp = c2.text_input("No. Telepon")
    prioritas = c3.checkbox("Pin / Prioritas Tinggi? ⭐")
    
    if st.button("Simpan Kontak"):
        st.success(f"Kontak {nama} {'(PENTING)' if prioritas else ''} tersimpan!")
        # Logika simpan ke database kontak bisa ditambahkan di sini
