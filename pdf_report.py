from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer,Image
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
P=colors.HexColor('#72007E')
def build(logo,borrower,ref,principal,pre,ctl,rows):
 out=BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=8*mm,rightMargin=8*mm,topMargin=8*mm,bottomMargin=8*mm);s=getSampleStyleSheet();s.add(ParagraphStyle(name='T',parent=s['Title'],textColor=P,fontSize=17));story=[Image(str(logo),width=50*mm,height=15*mm),Paragraph('Loan Repayment Schedule',s['T']),Spacer(1,3*mm)]
 meta=[['Borrower',borrower or '-','Reference',ref or '-'],['Principal',f'{principal:,.2f}','Initial EMI',f"{ctl['initial_emi']:,.2f}"],['Pre-EMI',f'{pre:,.2f}','Total Interest',f"{ctl['total_interest']:,.2f}"],['Part Prepayments',f"{ctl['total_prepayment']:,.2f}",'Control',ctl['status']]];t=Table(meta,colWidths=[30*mm,55*mm,35*mm,55*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#F2E8F4')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#F2E8F4')),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('PADDING',(0,0),(-1,-1),5)]));story += [t,Spacer(1,4*mm)]
 data=[['EMI #','Due Date','ROI (% p.a.)','Interest Component','Principal Component','EMI','Closing Principal']]+[[r.emi_no,r.due_date.strftime('%d-%m-%Y'),f'{r.roi*100:.3f}%',f'{r.interest_component:,.2f}',f'{r.principal_component:,.2f}',f'{r.emi:,.2f}',f'{r.closing_principal:,.2f}'] for r in rows];t=Table(data,repeatRows=1,colWidths=[15*mm,27*mm,27*mm,36*mm,38*mm,30*mm,38*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),P),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#FAF6FB')]),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('ALIGN',(2,1),(-1,-1),'RIGHT'),('FONTSIZE',(0,0),(-1,-1),8)]));story.append(t);doc.build(story);return out.getvalue()
