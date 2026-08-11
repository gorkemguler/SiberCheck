#!/usr/bin/env python3
"""
SiberCheck - Toplu Domain Engelleme & Tehdit İstihbarat Sorgulama CLI
Command-line interface tool for bulk checking domains against siberguvenlik.gov.tr REST API.
"""

import argparse
import os
import sys
import time
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text

from core.domain_checker import BulkDomainChecker
from core.normalizer import clean_domain
from exporters.excel_exporter import generate_excel_report
from exporters.json_exporter import generate_csv_report, generate_json_report

console = Console()

BANNER = """
[bold cyan]================================================================================[/bold cyan]
[bold white]  SiberCheck — T.C. SİBER GÜVENLİK BAŞKANLIĞI TEHDİT İSTİHBARAT & DOMAIN SORGUSU [/bold white]
[bold cyan]  Resmî REST API Entegrasyonu (https://siberguvenlik.gov.tr/api/)                 [/bold cyan]
[bold cyan]================================================================================[/bold cyan]
"""

def read_input_domains(args) -> List[str]:
    """Reads domain inputs from CLI flags, files, stdin, or demo data."""
    domains = []
    
    if args.domain:
        domains.append(args.domain)
    
    if args.input:
        if not os.path.exists(args.input):
            console.print(f"[bold red]Hata:[/bold red] Giriş dosyası bulunamadı: {args.input}")
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    domains.append(line)
                    
    if args.demo:
        demo_path = os.path.join(os.path.dirname(__file__), "data", "sample_100_domains.txt")
        if os.path.exists(demo_path):
            with open(demo_path, "r", encoding="utf-8") as f:
                domains.extend([l.strip() for l in f if l.strip()])
            console.print(f"[bold green]✓ 100 Adet Örnek Domain Yüklendi ({demo_path})[/bold green]")
        else:
            console.print("[bold red]Hata:[/bold red] Örnek 100 domain dosyası bulunamadı.")
            sys.exit(1)

    if not sys.stdin.isatty() and not domains:
        for line in sys.stdin:
            line = line.strip()
            if line and not line.startswith("#"):
                domains.append(line)

    return domains

def main():
    parser = argparse.ArgumentParser(
        description="SiberCheck — T.C. Siber Güvenlik Başkanlığı API Toplu Domain Sorgulama Araçları",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("-d", "--domain", type=str, help="Tekil domain sorgula (Örn: example.com)")
    parser.add_argument("-i", "--input", type=str, help="Domain listesi içeren dosya yolu (.txt, .csv)")
    parser.add_argument("-o", "--output", type=str, help="Excel rapor çıktı dosya yolu (Örn: rapor.xlsx)")
    parser.add_argument("-j", "--json", type=str, help="JSON çıktı dosya yolu (Örn: rapor.json)")
    parser.add_argument("-c", "--csv", type=str, help="CSV çıktı dosya yolu (Örn: rapor.csv)")
    parser.add_argument("-t", "--threads", type=int, default=15, help="Eşzamanlı sorgu iş parçacığı sayısı (Varsayılan: 15)")
    parser.add_argument("-s", "--strict", action="store_true", help="Kesin (tam) domain eşleşmesi zorunlu kıl")
    parser.add_argument("--demo", action="store_true", help="100 adet örnek domain ile test sorgusu çalıştır")
    parser.add_argument("--web", action="store_true", help="Yerel Web Arayüzünü (FastAPI Localhost Web UI) Başlat")

    args = parser.parse_args()

    if args.web:
        console.print("[bold cyan]🚀 SiberCheck Yerel Web Arayüzü Başlatılıyor...[/bold cyan]")
        import uvicorn
        from web.app import app
        uvicorn.run(app, host="127.0.0.1", port=8000)
        return

    console.print(BANNER)

    domains = read_input_domains(args)
    if not domains:
        console.print("[bold yellow]Kullanım Örnekleri:[/bold yellow]")
        console.print("  1. 100 Domain Test Sorgusu : [bold green]python3 siber_sorgu.py --demo -o rapor.xlsx[/bold green]")
        console.print("  2. Dosyadan Toplu Sorgu   : [bold green]python3 siber_sorgu.py -i domains.txt -o rapor.xlsx -j rapor.json[/bold green]")
        console.print("  3. Tek Domain Sorgu       : [bold green]python3 siber_sorgu.py -d test.com[/bold green]")
        console.print("  4. Web Arayüzünü Başlat   : [bold green]python3 siber_sorgu.py --web[/bold green]\n")
        sys.exit(0)

    checker = BulkDomainChecker(max_threads=args.threads, strict_match=args.strict)
    
    console.print(f"[bold cyan]🔍 Toplam [white]{len(domains)}[/white] domain sorgulanıyor (İş Parçacığı: {args.threads})...[/bold cyan]\n")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    )

    task_id = progress.add_task("[yellow]Sorgulanıyor...[/yellow]", total=len(set(domains)))
    
    def on_progress(completed, total, res):
        status_sym = "[bold red]✖[/bold red]" if res["is_blocked"] else "[bold green]✔[/bold green]"
        dom_text = res["domain"][:30].ljust(30)
        progress.update(task_id, completed=completed, description=f"{status_sym} {dom_text}")

    with progress:
        report = checker.scan_domains(domains, progress_callback=on_progress)

    summary = report["summary"]
    results = report["results"]

    console.print("\n")
    
    summary_panel = Panel(
        f"[bold white]Taranan Domain:[/bold white] {summary['total_scanned']} | "
        f"[bold red]Engellenmiş / Zararlı:[/bold red] {summary['blocked_count']} | "
        f"[bold green]Temiz / Safe:[/bold green] {summary['clean_count']} | "
        f"[bold yellow]Yüksek Kritik (1-3):[/bold yellow] {summary['high_criticality_count']} | "
        f"[bold cyan]Süre:[/bold cyan] {summary['duration_seconds']}s ({summary['domains_per_second']} req/sec)",
        title="[bold yellow]SİBERCHECK TARAMA SONUÇ ÖZETİ[/bold yellow]",
        border_style="cyan"
    )
    console.print(summary_panel)

    blocked_items = [r for r in results if r["is_blocked"]]
    if blocked_items:
        table = Table(title=f"🚨 ENGELLENMİŞ / ZARARLI ALAN ADLARI ({len(blocked_items)} Adet)", show_header=True, header_style="bold white on red")
        table.add_column("No", justify="center", style="cyan", no_wrap=True)
        table.add_column("Domain Adı", style="bold white")
        table.add_column("Durum", justify="center", style="bold red")
        table.add_column("Kritiklik", justify="center", style="yellow")
        table.add_column("Kategori / Açıklama", style="magenta")
        table.add_column("Kaynak", style="blue")
        table.add_column("Tespit Tarihi", style="dim")

        for idx, item in enumerate(blocked_items[:25], start=1):
            threats = item.get("threats", [])
            t0 = threats[0] if threats else {}
            crit = str(item.get("max_criticality") or "-")
            
            table.add_row(
                str(idx),
                item["domain"],
                "ENGELLENMİŞ",
                crit,
                t0.get("desc_text", "-"),
                t0.get("source_text", "-"),
                t0.get("date", "-")
            )
        
        console.print(table)
        if len(blocked_items) > 25:
            console.print(f"[dim]* Terminalde ilk 25 engellenmiş kayıt gösterildi. Tamamını görmek için Excel/JSON çıktısını inceleyin.[/dim]\n")
    else:
        console.print("[bold green]✔ Taranan domainler arasında herhangi bir zararlı / engellenmiş alan adı bulunamadı.[/bold green]\n")

    excel_path = args.output
    if not excel_path and not args.json and not args.csv and not args.domain:
        excel_path = "sibercheck_sorgu_sonuclari.xlsx"
        
    if excel_path:
        generate_excel_report(report, excel_path)
        console.print(f"[bold green]📊 Excel Raporu Başarıyla Oluşturuldu:[/bold green] [underline white]{os.path.abspath(excel_path)}[/underline white]")

    if args.json:
        generate_json_report(report, args.json)
        console.print(f"[bold green]📄 JSON Raporu Başarıyla Oluşturuldu:[/bold green] [underline white]{os.path.abspath(args.json)}[/underline white]")

    if args.csv:
        generate_csv_report(report, args.csv)
        console.print(f"[bold green]📝 CSV Raporu Başarıyla Oluşturuldu:[/bold green] [underline white]{os.path.abspath(args.csv)}[/underline white]")

    console.print("\n[bold cyan]Sorgulama İşlemi Tamamlandı.[/bold cyan]")

if __name__ == "__main__":
    main()
