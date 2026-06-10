import { useState } from "react"

import { api } from "../services/api"

const DOC_TYPES = ["lead", "insurance", "cleanup", "sold", "commission", "credit"]
const APPROVAL_SECRET_CONFIGURED = Boolean(String(import.meta.env.VITE_SERVICE_VIDEO_APPROVAL_SECRET || "").trim())

export default function Paperwork() {
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState("lead")
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoCustomerId, setVideoCustomerId] = useState<number>(1)
  const [videoSalespersonId, setVideoSalespersonId] = useState<number>(1)
  const [videoResult, setVideoResult] = useState<any>(null)
  const [videoStatus, setVideoStatus] = useState("")

  const [vin, setVin] = useState("")
  const [schedMake, setSchedMake] = useState("Toyota")
  const [schedModel, setSchedModel] = useState("Camry")
  const [schedYear, setSchedYear] = useState<number>(2022)
  const [schedStatus, setSchedStatus] = useState("")

  const submit = async () => {
    if (!file) return
    setLoading(true)
    setError("")
    try {
      const data = await api.ingestDocument(file, docType)
      setResult(data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Upload failed")
    } finally {
      setLoading(false)
    }
  }

  const uploadVideo = async () => {
    if (!videoFile) return
    setVideoStatus("")
    try {
      const data = await api.uploadServiceVideo(videoFile, {
        customer_id: videoCustomerId,
        salesperson_id: videoSalespersonId,
      })
      setVideoResult(data)
      setVideoStatus("Service walkaround uploaded.")
    } catch (e: any) {
      setVideoStatus(e?.response?.data?.detail || e?.message || "Video upload failed")
    }
  }

  const approveVideo = async (approved: boolean) => {
    if (!videoResult?.video_id) return
    if (!APPROVAL_SECRET_CONFIGURED) {
      setVideoStatus("Video approval is disabled: VITE_SERVICE_VIDEO_APPROVAL_SECRET is not configured.")
      return
    }

    setVideoStatus("")
    try {
      const data = await api.approveServiceVideo(videoResult.video_id, approved, { reviewer: "sales-ui" })
      setVideoResult((prev: any) => ({ ...prev, approval_status: data.approval_status }))
      setVideoStatus(`Video ${data.approval_status}.`)
    } catch (e: any) {
      if (e?.response?.status === 501) {
        setVideoStatus("Approval webhook is disabled on the backend. Set SERVICE_VIDEO_APPROVAL_SECRET and redeploy.")
        return
      }
      setVideoStatus(e?.response?.data?.detail || e?.message || "Approval webhook failed")
    }
  }

  const downloadSchedulePdf = async () => {
    setSchedStatus("")
    try {
      const blob = await api.getMaintenanceSchedulePdf(
        vin.trim()
          ? { vin: vin.trim() }
          : { make: schedMake, model: schedModel, year: schedYear }
      )
      const url = URL.createObjectURL(blob)
      window.open(url, "_blank", "noopener,noreferrer")
      setSchedStatus("Maintenance PDF generated.")
    } catch (e: any) {
      setSchedStatus(e?.response?.data?.detail || e?.message || "Unable to generate maintenance PDF")
    }
  }

  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-lg font-semibold">EasyOCR Paperwork Intake</h3>
        <p className="text-sm text-slate-600 mt-1">Upload a dealership form and extract fields directly into CSV workflows.</p>

        <div className="mt-4 space-y-2">
          <label className="text-sm text-slate-700" htmlFor="paperwork-file">Document image</label>
          <input
            id="paperwork-file"
            title="Document image"
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <label className="text-sm text-slate-700" htmlFor="paperwork-type">Document type</label>
          <select id="paperwork-type" title="Document type" className="rounded border p-2" value={docType} onChange={(e) => setDocType(e.target.value)}>
            {DOC_TYPES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <button onClick={submit} disabled={!file || loading} className="rounded-lg bg-imperial-secondary text-white px-4 py-2 font-semibold">
            {loading ? "Processing..." : "Ingest Document"}
          </button>
          {error && <p className="text-sm text-imperial-danger">{error}</p>}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-lg font-semibold">Extracted Output</h3>
        <pre className="mt-3 text-xs bg-slate-900 text-slate-100 p-3 rounded-lg overflow-auto max-h-[420px]">
          {JSON.stringify(result || { status: "waiting", note: "Run ingestion to view parsed data." }, null, 2)}
        </pre>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
        <h3 className="text-lg font-semibold">Service Video Walkaround</h3>
        <p className="text-sm text-slate-600 mt-1">Upload a video, generate signed URL, and trigger approval webhook.</p>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
          <input type="file" accept="video/*" aria-label="Service video file" onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
          <input type="number" aria-label="Video customer id" value={videoCustomerId} onChange={(e) => setVideoCustomerId(Number(e.target.value || 1))} className="rounded border px-3 py-2" placeholder="Customer ID" />
          <input type="number" aria-label="Video salesperson id" value={videoSalespersonId} onChange={(e) => setVideoSalespersonId(Number(e.target.value || 1))} className="rounded border px-3 py-2" placeholder="Salesperson ID" />
          <button type="button" onClick={uploadVideo} className="rounded-lg bg-imperial-secondary text-white px-4 py-2 font-semibold">Upload Walkaround</button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => approveVideo(true)} disabled={!videoResult?.video_id || !APPROVAL_SECRET_CONFIGURED} className="rounded-lg border border-green-300 bg-green-50 px-3 py-2 text-sm font-semibold text-green-800 disabled:opacity-50">Approve Video</button>
          <button type="button" onClick={() => approveVideo(false)} disabled={!videoResult?.video_id || !APPROVAL_SECRET_CONFIGURED} className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800 disabled:opacity-50">Reject Video</button>
          {videoResult?.signed_url && (
            <a className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700" href={videoResult.signed_url} target="_blank" rel="noreferrer">
              Open Signed Video URL
            </a>
          )}
        </div>
        {!APPROVAL_SECRET_CONFIGURED && (
          <p className="mt-2 text-sm font-semibold text-amber-700">
            Approval buttons are disabled until VITE_SERVICE_VIDEO_APPROVAL_SECRET is configured.
          </p>
        )}
        {videoStatus && <p className="mt-2 text-sm font-semibold text-slate-700">{videoStatus}</p>}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
        <h3 className="text-lg font-semibold">Maintenance Schedule PDF</h3>
        <p className="text-sm text-slate-600 mt-1">Generate a reportlab schedule by VIN or by make/model/year.</p>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
          <input value={vin} onChange={(e) => setVin(e.target.value)} aria-label="VIN for maintenance schedule" placeholder="VIN (optional)" className="rounded border px-3 py-2" />
          <input value={schedMake} onChange={(e) => setSchedMake(e.target.value)} aria-label="Schedule make" placeholder="Make" className="rounded border px-3 py-2" />
          <input value={schedModel} onChange={(e) => setSchedModel(e.target.value)} aria-label="Schedule model" placeholder="Model" className="rounded border px-3 py-2" />
          <input type="number" value={schedYear} onChange={(e) => setSchedYear(Number(e.target.value || 2022))} aria-label="Schedule year" placeholder="Year" className="rounded border px-3 py-2" />
        </div>
        <button type="button" onClick={downloadSchedulePdf} className="mt-3 rounded-lg bg-imperial-primary text-white px-4 py-2 font-semibold">Generate Maintenance PDF</button>
        {schedStatus && <p className="mt-2 text-sm font-semibold text-slate-700">{schedStatus}</p>}
      </div>
    </section>
  )
}
