from documents.pdf import render_pdf


def render_smeta_pdf(context: dict) -> bytes:
    return render_pdf('smety/pdf/smeta.html', context)
