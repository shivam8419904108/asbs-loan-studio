from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer,Image
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
P='#72007E'
def pdf_bytes(logo,payload,pre,ctl,rows):
    out=BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=8*mm,rightMargin=8*mm,topMargin=8*mm,bottomMargin=8*mm);s=getSampleStyleSheet();s.add(ParagraphStyle(name='T',parent=s['Title'],textColor=colors.HexColor(P),fontSize=17));story=[]
    if logo.exists():story.append(Image(str(logo),width=50*mm,height=15*mm))
    story += [Paragraph('Loan Repayment Schedule',s['T']),Spacer(1,3*mm)]
    meta=[['Borrower',payload.get('borrower') or '-','Reference',payload.get('ref') or '-'],['Principal',f"{payload['principal']:,.2f}",'Initial EMI',f"{ctl['initial_emi']:,.2f}"],['Pre-EMI',f'{pre:,.2f}','Total Interest',f"{ctl['total_interest']:,.2f}"],['Part Prepayments',f"{ctl['total_prepayment']:,.2f}",'Control',ctl['status']]]
    t=Table(meta,colWidths=[30*mm,55*mm,35*mm,55*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#F2E8F4')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#F2E8F4')),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('PADDING',(0,0),(-1,-1),5)]));story += [t,Spacer(1,4*mm)]
    data=[['EMI #','Due Date','ROI (% p.a.)','Interest Component','Principal Component','EMI','Closing Principal']]+[[r.emi_no,r.due_date.strftime('%d-%m-%Y'),f'{r.roi*100:.3f}%',f'{r.interest_component:,.2f}',f'{r.principal_component:,.2f}',f'{r.emi:,.2f}',f'{r.closing_principal:,.2f}'] for r in rows]
    t=Table(data,repeatRows=1,colWidths=[15*mm,27*mm,27*mm,36*mm,38*mm,30*mm,38*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(P)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#FAF6FB')]),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('ALIGN',(2,1),(-1,-1),'RIGHT'),('FONTSIZE',(0,0),(-1,-1),8)]));story.append(t);doc.build(story);return out.getvalue()
def excel_bytes(payload,pre,ctl,rows,roi_events,pp_events):
    wb=Workbook();ws=wb.active;ws.title='EMI Schedule';ws.sheet_view.showGridLines=False;ws.merge_cells('A1:I1');ws['A1']='ASBS & CO - Loan Repayment Schedule';ws['A1'].font=Font(size=17,bold=True,color='FFFFFF');ws['A1'].fill=PatternFill('solid',fgColor=P[1:]);ws['A1'].alignment=Alignment(horizontal='center')
    meta=[('Borrower',payload.get('borrower','')),('Reference',payload.get('ref','')),('Principal',payload['principal']),('Initial EMI',ctl['initial_emi']),('Pre-EMI',pre),('Total Interest',ctl['total_interest']),('Part Prepayments',ctl['total_prepayment']),('Payoff Date',ctl['payoff_date']),('Control Status',ctl['status']),('Annual Basis','365 days only')]
    for i,(k,v) in enumerate(meta,3):ws.cell(i,1,k).font=Font(bold=True,color=P[1:]);ws.cell(i,2,v)
    hdr=14;heads=['EMI #','Due Date','Opening Principal','ROI (% p.a.)','Interest Component','Principal Component','EMI','Part Prepayment','Closing Principal']
    for j,h in enumerate(heads,1):c=ws.cell(hdr,j,h);c.fill=PatternFill('solid',fgColor=P[1:]);c.font=Font(bold=True,color='FFFFFF')
    for i,r in enumerate(rows,hdr+1):
        vals=[r.emi_no,r.due_date,r.opening_principal,r.roi,r.interest_component,r.principal_component,r.emi,r.part_prepayment,r.closing_principal]
        for j,v in enumerate(vals,1):ws.cell(i,j,v)
        ws.cell(i,2).number_format='dd-mm-yyyy';ws.cell(i,4).number_format='0.000%'
        for j in [3,5,6,7,8,9]:ws.cell(i,j).number_format='₹#,##0.00;[Red](₹#,##0.00);-'
    ws.freeze_panes='A15';ws.auto_filter.ref=f'A14:I{14+len(rows)}'
    for j,w in enumerate([10,15,20,15,20,20,16,18,20],1):ws.column_dimensions[get_column_letter(j)].width=w
    for title,events,heads in [('ROI Changes',roi_events,['Effective Date','New ROI (% p.a.)','Note']),('Part Prepayments',pp_events,['Date','Amount','Effect','Note'])]:
        sh=wb.create_sheet(title)
        for j,h in enumerate(heads,1):c=sh.cell(1,j,h);c.fill=PatternFill('solid',fgColor=P[1:]);c.font=Font(bold=True,color='FFFFFF')
        for i,e in enumerate(events,2):
            vals=[e.get('date'),e.get('rate'),e.get('note')] if title=='ROI Changes' else [e.get('date'),e.get('amount'),e.get('effect'),e.get('note')]
            for j,v in enumerate(vals,1):sh.cell(i,j,v)
    out=BytesIO();wb.save(out);return out.getvalue()
