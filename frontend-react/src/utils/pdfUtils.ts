import html2pdf from 'html2pdf.js';

type PdfOrientation = 'portrait' | 'landscape';
type ImageType = 'jpeg' | 'png' | 'webp';

interface ExportPdfOptions {
  elementId: string;
  filename: string;
  orientation?: PdfOrientation;
  margin?: number;
  scale?: number;
}

export async function exportElementToPdf({
  elementId,
  filename,
  orientation = 'portrait',
  margin = 10,
  scale = 2,
}: ExportPdfOptions): Promise<void> {
  const element = document.getElementById(elementId);

  if (!element) {
    throw new Error(`Element with id "${elementId}" not found`);
  }

  const options = {
    margin,
    filename,
    image: {
      type: 'jpeg' as ImageType,
      quality: 0.98,
    },
    html2canvas: {
      scale,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff',
    },
    jsPDF: {
      unit: 'mm',
      format: 'a4',
      orientation,
    },
    pagebreak: {
      mode: ['css', 'legacy'] as Array<'css' | 'legacy' | 'avoid-all'>,
      avoid: ['.print-avoid-break', '.print-sticker', '.print-layout-board'],
    },
  };

  await html2pdf().set(options).from(element).save();
}

export async function exportResultsPdf(elementId = 'printable-results', reportId?: string) {
  const filename = reportId ? `results_${reportId}.pdf` : `results_${Date.now()}.pdf`;
  return exportElementToPdf({
    elementId,
    filename,
    orientation: 'portrait',
    margin: 8,
    scale: 2,
  });
}

export async function exportStickersPdf(elementId = 'printable-stickers', reportId?: string) {
  const filename = reportId ? `stickers_${reportId}.pdf` : `stickers_${Date.now()}.pdf`;
  return exportElementToPdf({
    elementId,
    filename,
    orientation: 'portrait',
    margin: 8,
    scale: 2,
  });
}