import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, apiTout, type Page, type Site } from '../api'
import BoutonExcel from '../BoutonExcel'
import { montant } from '../achats/commandes'
import { dateFr } from '../achats/types'
import { nombre } from '../stock/types'

type Plein = { id: number; materiel: number; materiel_nom: string; site_nom: string; date: string; litres: string; montant: string | null; compteur_heures: string | null; compteur_km: number | null; lieu: string; conducteur: string; reference: string; saisi_par: string }
type Engin = { id: number; code: string; designation: string; etat: string }
type Ligne = { id: number; code: string; designation: string; site_nom: string; pleins: number; litres: string; montant: string; km: number | null; consommation_100km: string | null; heures: string | null; consommation_heure: string | null }
type Synthese = { lignes: Ligne[]; total: { pleins: number; litres: string; montant: string } }

const jour = (d: Date) => d.toLocaleDateString('fr-CA')
const VIDE = { materiel: '', date: jour(new Date()), litres: '', montant: '', compteur_heures: '', compteur_km: '', lieu: '', conducteur: '', reference: '' }

/** Pleins de carburant du parc et consommation par équipement. */
export default function Carburant({ peutSaisir }: { peutSaisir: boolean }) {
  const [filtre, setFiltre] = useState({ debut: `${new Date().getFullYear()}-01-01`, fin: jour(new Date()), site: '' })
  const [sites, setSites] = useState<Site[]>([])
  const [engins, setEngins] = useState<Engin[]>([])
  const [pleins, setPleins] = useState<Plein[] | null>(null)
  const [synthese, setSynthese] = useState<Synthese | null>(null)
  const [f, setF] = useState(VIDE)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => {
    const q = new URLSearchParams({ date__gte: filtre.debut, date__lte: filtre.fin, ...(filtre.site ? { materiel__site: filtre.site } : {}) })
    api<Page<Plein>>(`/technique/pleins/?${q}&page_size=100`).then((p) => setPleins(p.results)).catch((e: Error) => setErreur(e.message))
    api<Synthese>(`/technique/pleins/synthese/?${new URLSearchParams(Object.entries(filtre).filter(([, v]) => v !== ''))}`).then(setSynthese).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    apiTout<Engin>('/technique/materiels/').then((l) => setEngins(l.filter((m) => m.etat !== 'REFORME'))).catch(() => undefined)
  }, [])
  const maj = (c: string, v: string) => setF({ ...f, [c]: v })
  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setEnCours(true)
    setErreur('')
    try {
      await api<Plein>('/technique/pleins/', { method: 'POST', body: JSON.stringify({ ...f, montant: f.montant || null, compteur_heures: f.compteur_heures || null, compteur_km: f.compteur_km || null }) })
      setF({ ...VIDE, date: f.date, lieu: f.lieu })
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  return (
    <>
      <div className="barre">
        <h2>Carburant</h2>
        <BoutonExcel chemin="/technique/pleins/" filtres={{ date__gte: filtre.debut, date__lte: filtre.fin, materiel__site: filtre.site }} nom="pleins-carburant" onErreur={setErreur} />
      </div>
      {peutSaisir && (
        <form className="fiche" onSubmit={enregistrer}>
          <fieldset>
            <legend>Saisir un plein</legend>
            <div className="grille">
              <label>Matériel<select required value={f.materiel} onChange={(e) => maj('materiel', e.target.value)}><option value="">Choisir…</option>{engins.map((m) => <option key={m.id} value={m.id}>{m.code} · {m.designation}</option>)}</select></label>
              <label>Date<input type="date" required max={jour(new Date())} value={f.date} onChange={(e) => maj('date', e.target.value)} /></label>
              <label>Litres<input type="number" required min="0.1" step="0.1" value={f.litres} onChange={(e) => maj('litres', e.target.value)} /></label>
              <label>Montant payé (XOF)<input type="number" min="0" step="1" value={f.montant} onChange={(e) => maj('montant', e.target.value)} /></label>
              <label>Compteur (km)<input type="number" min="0" step="1" value={f.compteur_km} onChange={(e) => maj('compteur_km', e.target.value)} /></label>
              <label>Compteur (heures)<input type="number" min="0" step="0.1" value={f.compteur_heures} onChange={(e) => maj('compteur_heures', e.target.value)} /></label>
              <label>Station ou cuve<input maxLength={120} value={f.lieu} onChange={(e) => maj('lieu', e.target.value)} /></label>
              <label>Conducteur ou opérateur<input maxLength={120} value={f.conducteur} onChange={(e) => maj('conducteur', e.target.value)} /></label>
              <label>N° de ticket ou de bon<input maxLength={60} value={f.reference} onChange={(e) => maj('reference', e.target.value)} /></label>
            </div>
            <p className="aide">Relevez le compteur à chaque plein : c'est lui qui donne la consommation.</p>
            <div className="actions"><button disabled={enCours}>Enregistrer le plein</button></div>
          </fieldset>
        </form>
      )}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <h3>Consommation par équipement</h3>
      <div className="grille filtres large">
        <label>Du<input type="date" value={filtre.debut} onChange={(e) => setFiltre({ ...filtre, debut: e.target.value })} /></label>
        <label>Au<input type="date" value={filtre.fin} onChange={(e) => setFiltre({ ...filtre, fin: e.target.value })} /></label>
        <label>Site<select value={filtre.site} onChange={(e) => setFiltre({ ...filtre, site: e.target.value })}><option value="">Tous</option>{sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select></label>
      </div>
      {synthese && synthese.lignes.length === 0 && <p className="aide">Aucun plein sur cette période.</p>}
      {synthese && synthese.lignes.length > 0 && (
        <>
          <p>{synthese.total.pleins} plein(s) · <strong>{nombre(synthese.total.litres)} litres</strong> · {montant(synthese.total.montant)}</p>
          <div className="defilant">
            <table>
              <thead><tr><th>Équipement</th><th>Site</th><th className="nombre">Pleins</th><th className="nombre">Litres</th><th className="nombre">Montant</th><th className="nombre">Parcouru</th><th className="nombre">Consommation</th></tr></thead>
              <tbody>
                {synthese.lignes.map((l) => (
                  <tr key={l.id}>
                    <td><a href={`#/parc/${l.id}`}>{l.code}</a> · {l.designation}</td><td>{l.site_nom}</td>
                    <td className="nombre">{l.pleins}</td><td className="nombre">{nombre(l.litres)}</td><td className="nombre">{montant(l.montant)}</td>
                    <td className="nombre">{[l.km !== null && `${nombre(l.km)} km`, l.heures !== null && `${nombre(l.heures)} h`].filter(Boolean).join(' · ') || '–'}</td>
                    <td className="nombre">{[l.consommation_100km && `${nombre(l.consommation_100km)} l/100 km`, l.consommation_heure && `${nombre(l.consommation_heure)} l/h`].filter(Boolean).join(' · ') || '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <h3>Pleins de la période</h3>
      {pleins?.length === 0 && <p className="aide">Aucun plein.</p>}
      {pleins && pleins.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Date</th><th>Matériel</th><th className="nombre">Litres</th><th className="nombre">Montant</th><th>Compteur</th><th>Station, conducteur</th></tr></thead>
            <tbody>
              {pleins.map((p) => (
                <tr key={p.id}>
                  <td>{dateFr(p.date)}</td><td>{p.materiel_nom}</td><td className="nombre">{nombre(p.litres)}</td><td className="nombre">{p.montant ? montant(p.montant) : ''}</td>
                  <td>{[p.compteur_km !== null && `${nombre(p.compteur_km)} km`, p.compteur_heures && `${nombre(p.compteur_heures)} h`].filter(Boolean).join(' · ')}</td>
                  <td>{[p.lieu, p.conducteur, p.reference].filter(Boolean).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
