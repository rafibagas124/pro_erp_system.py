import streamlit as st
import pandas as pd
import sqlite3
import qrcode
import base64
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from datetime import datetime
from io import BytesIO
import time
import hashlib

# --- 1. KONFIGURASI HALAMAN & TEMA ---
st.set_page_config(page_title="Ultra ERP System", page_icon="💎", layout="wide")

# Custom CSS untuk Font & Tampilan Modern (Sesuai Request)
def set_font(font_name):
    st.markdown(f"""
    <style>
        html, body, [class*="css"] {{ font-family: '{font_name}', sans-serif; }}
        .stMetric {{ background-color: #1E1E1E; padding: 10px; border-radius: 10px; border: 1px solid #333; }}
        .big-font {{ font-size:20px !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEM KEAMANAN (LOGIN) ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == "admin123": # Password Default
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Hapus password dari session
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Input Password Pertama kali
        st.text_input("🔒 Masukkan Password Sistem:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password salah
        st.text_input("🔒 Masukkan Password Sistem:", type="password", on_change=password_entered, key="password")
        st.error("Password salah.")
        return False
    else:
        # Password benar
        return True

if not check_password():
    st.stop() # Berhenti jika belum login

# --- 3. DATABASE CONNECTION ---
def init_db():
    conn = sqlite3.connect('ultra_erp.db')
    c = conn.cursor()
    # Tabel Super Lengkap
    c.execute('''CREATE TABLE IF NOT EXISTS transaksi 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tanggal TEXT, kategori TEXT, 
                 item TEXT, jumlah REAL, harga REAL, total REAL, status TEXT, 
                 prioritas TEXT, user TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 4. HELPER FUNCTIONS ---
def get_data():
    conn = sqlite3.connect('ultra_erp.db')
    df = pd.read_sql("SELECT * FROM transaksi", conn)
    conn.close()
    return df

def save_data_bulk(df_new):
    conn = sqlite3.connect('ultra_erp.db')
    # Hapus data lama ganti baru (Metode Sync Excel)
    df_new.to_sql('transaksi', conn, if_exists='replace', index=False)
    conn.close()

# --- 5. SIDEBAR SETTINGS ---
with st.sidebar:
    st.title("💎 ULTRA ERP")
    st.write(f"Login: Admin | {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    
    # Fitur Ganti Font
    pilih_font = st.selectbox("🔤 Gaya Tulisan", ["Roboto", "Times New Roman", "Courier New", "Verdana"])
    set_font(pilih_font)
    
    # Menu Navigasi
    menu = st.radio("Navigasi", ["Dashboard Analisa", "Spreadsheet Mode (Excel)", "Invoice & PDF", "QR Code & Tools"])

# --- 6. MAIN CONTENT ---

# === DASHBOARD (GRAFIK ANALISA OTOMATIS) ===
if menu == "Dashboard Analisa":
    st.header(f"📊 Dashboard Analitik ({pilih_font})")
    
    df = get_data()
    
    if df.empty:
        st.info("Data masih kosong. Silakan input di menu 'Spreadsheet Mode'.")
    else:
        # 1. Notifikasi Pengingat (Reminder)
        hari_ini = datetime.now().strftime("%Y-%m-%d")
        if not df[df['tanggal'] == hari_ini].empty:
            st.toast(f"🔔 PENGINGAT: Ada {len(df[df['tanggal'] == hari_ini])} transaksi terjadwal hari ini!", icon="📅")

        # 2. KPI Cards (Summary)
        col1, col2, col3, col4 = st.columns(4)
        total_uang = df['total'].sum()
        jml_transaksi = len(df)
        item_prioritas = len(df[df['prioritas'] == 'Tinggi'])
        
        col1.metric("Total Keuangan", f"Rp {total_uang:,.0f}")
        col2.metric("Total Transaksi", jml_transaksi)
        col3.metric("🔥 Prioritas Tinggi", item_prioritas)
        col4.metric("User Aktif", "Admin, Staff 1, Staff 2")

        # 3. Grafik Analisa Otomatis (Plotly)
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Tren Pemasukan (Line Chart)")
            # Grouping data berdasarkan tanggal
            trend = df.groupby('tanggal')['total'].sum().reset_index()
            fig_line = px.line(trend, x='tanggal', y='total', markers=True, template="plotly_dark")
            st.plotly_chart(fig_line, use_container_width=True)
            
        with c2:
            st.subheader("Sebaran Kategori (Pie Chart)")
            fig_pie = px.pie(df, names='kategori', values='total', template="plotly_dark", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Analisa Performa Barang (Bar Chart)")
        fig_bar = px.bar(df, x='item', y='jumlah', color='status', template="plotly_dark")
        st.plotly_chart(fig_bar, use_container_width=True)

# === SPREADSHEET MODE (FITUR PARALEL & RUMUS) ===
elif menu == "Spreadsheet Mode (Excel)":
    st.header("📝 Input Data Masal (Excel Mode)")
    st.caption("Di sini Anda bisa copy-paste dari Excel, mengedit tabel, filter, sort, dan pivot.")
    
    # Load Data dari Database
    df_current = get_data()
    
    if df_current.empty:
        # Template awal jika kosong
        df_current = pd.DataFrame({
            'tanggal': [datetime.now().strftime('%Y-%m-%d')],
            'kategori': ['Pemasukan'],
            'item': ['Contoh Barang'],
            'jumlah': [10],
            'harga': [5000],
            'total': [50000],
            'status': ['Lunas'],
            'prioritas': ['Normal'],
            'user': ['Admin']
        })

    # KONFIGURASI AG-GRID (RAHASIA EXCEL DI STREAMLIT)
    gb = GridOptionsBuilder.from_dataframe(df_current)
    gb.configure_pagination(paginationAutoPageSize=True) # Halaman otomatis
    gb.configure_side_bar() # Sidebar filter kanan
    gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
    
    # Warnai Tabel (Conditional Formatting)
    js_code = """
    function(params) {
        if (params.value == 'Tinggi') {
            return {
                'color': 'white',
                'backgroundColor': '#ff4b4b'
            }
        }
    };
    """
    gb.configure_column("prioritas", cellStyle=st.text_code(js_code))
    gridOptions = gb.build()

    # Tampilkan Tabel Excel
    grid_response = AgGrid(
        df_current, 
        gridOptions=gridOptions,
        data_return_mode='AS_INPUT', 
        update_mode='MODEL_CHANGED', 
        fit_columns_on_grid_load=True,
        theme='balham', # Tema mirip Excel
        enable_enterprise_modules=True,
        height=400, 
        width='100%',
        allow_unsafe_jscode=True
    )

    # Tombol Simpan Perubahan
    if st.button("💾 SIMPAN SEMUA PERUBAHAN KE DATABASE"):
        updated_df = grid_response['data']
        # Hitung ulang rumus Total otomatis (Harga x Jumlah)
        updated_df['total'] = pd.to_numeric(updated_df['jumlah']) * pd.to_numeric(updated_df['harga'])
        
        save_data_bulk(updated_df)
        st.success("Database berhasil diperbarui! Semua karyawan bisa melihat data baru.")
        st.experimental_rerun()

    # Rumus Pivot Cepat
    st.divider()
    st.subheader("🧮 Rumus Cepat (Pivot)")
    col_sum, col_avg, col_max = st.columns(3)
    col_sum.metric("SUM (Total Uang)", f"Rp {df_current['total'].sum():,.0f}")
    col_avg.metric("AVERAGE (Rata-rata)", f"Rp {df_current['total'].mean():,.0f}")
    col_max.metric("MAX (Transaksi Terbesar)", f"Rp {df_current['total'].max():,.0f}")

# === INVOICE MAKER ===
elif menu == "Invoice & PDF":
    st.header("🖨️ Cetak Dokumen")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Buat Invoice Customer")
        inv_nama = st.text_input("Nama Customer")
        inv_items = st.text_area("List Barang (Pisahkan dengan koma)", "Laptop Asus, Mouse Logitech")
        inv_total = st.number_input("Total Tagihan", 0)
        
        if st.button("Generate Invoice PDF"):
            # Simple PDF Generator Logic
            pdf = f"INVOICE\nKepada: {inv_nama}\nTanggal: {datetime.now()}\n\nBarang: {inv_items}\n\nTOTAL: Rp {inv_total}"
            # Di aplikasi nyata kita pakai FPDF, ini simulasi text file biar simple
            st.download_button("Download PDF", pdf, file_name=f"Invoice_{inv_nama}.txt")

    with col2:
        st.subheader("Backup Data Lengkap")
        conn = sqlite3.connect('ultra_erp.db')
        df_download = pd.read_sql("SELECT * FROM transaksi", conn)
        conn.close()
        
        # Download Excel
        towrite = BytesIO()
        df_download.to_excel(towrite, index=False)
        towrite.seek(0)
        st.download_button("📥 Download Excel Backup", towrite, "backup_data.xlsx")
        
        # Download CSV
        st.download_button("📥 Download CSV", df_download.to_csv(index=False), "backup_data.csv")

# === QR TOOLS ===
elif menu == "QR Code & Tools":
    st.header("📱 QR Generator & Link")
    
    text_qr = st.text_input("Masukkan Link Data / Kode Barang / Nama:")
    nama_file_qr = st.text_input("Nama File QR:", "kode_qr")
    
    if st.button("Buat QR Code"):
        img = qrcode.make(text_qr)
        buf = BytesIO()
        img.save(buf)
        byte_im = buf.getvalue()
        st.image(byte_im, width=200)
        st.download_button("Simpan Gambar QR", byte_im, f"{nama_file_qr}.png", "image/png")
        
    st.info("💡 Tips: Print QR ini dan tempel di gudang. Saat discan akan memunculkan teks/link yang kamu masukkan.")
