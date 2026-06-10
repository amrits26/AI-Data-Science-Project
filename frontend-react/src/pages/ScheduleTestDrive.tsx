import { useState } from "react"

export default function ScheduleTestDrive() {
  const [name, setName] = useState("")
  const [phone, setPhone] = useState("")
  const [vehicle, setVehicle] = useState("")
  const [date, setDate] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const submit = () => {
    if (!name.trim() || !phone.trim() || !vehicle.trim() || !date.trim()) return
    setSubmitted(true)
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="m-0 text-xl font-bold text-slate-900">Schedule Test Drive</h2>
      <p className="mt-1 text-sm text-slate-600">Choose your vehicle and preferred time, and our team will confirm by phone.</p>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <input aria-label="Customer name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" className="rounded-lg border border-slate-300 px-3 py-2" />
        <input aria-label="Phone number" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone number" className="rounded-lg border border-slate-300 px-3 py-2" />
        <input aria-label="Preferred vehicle" value={vehicle} onChange={(e) => setVehicle(e.target.value)} placeholder="Vehicle (e.g., 2022 Toyota Camry)" className="rounded-lg border border-slate-300 px-3 py-2" />
        <input aria-label="Preferred date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" />
      </div>

      <button type="button" onClick={submit} className="mt-4 rounded-lg bg-imperial-primary px-4 py-2 text-sm font-semibold text-white">
        Request Test Drive
      </button>

      {submitted && (
        <p className="mt-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm font-medium text-green-800">
          Request sent. A sales advisor will contact you shortly to confirm your slot.
        </p>
      )}
    </section>
  )
}
