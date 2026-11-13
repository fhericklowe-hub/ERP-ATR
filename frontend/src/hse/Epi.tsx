import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { dateFr } from '../achats/types'

type Dotation = {
  id: number; salarie: number; salarie_nom: string; matricule: string; site_nom: string; equipement: string; equipement_libelle: string; precision: string
  quantite: number; date_remise: string; a_renouveler_le: string | null; jours: number | null; remis_par_nom: string; observations: string
}
type Salarie = { id: number; nom: string; matricule: string; site_nom: string }

const EQUIPEMENTS = [['CASQUE', 'Casque'], ['CHAUSSURES', 'Chaussures de sécurité'], ['GANTS', 'Gants'], ['GILET', 'Gilet haute visibilité'],
  ['LUNETTES', 'Lunettes de protection'], ['AUDITIF', 'Protections auditives'], ['MASQUE', 'Masque'], ['HARNAIS', 'Harnais antichute'],
  ['TENUE', 'Tenue de travail'], ['AUTRE', 'Autre']]
const aujourdHui = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10)
const vide = () => ({ salarie: '', equipement: 'CASQUE', precision: '', quantite: 1, date_remise: aujourdHui(), a_renouveler_le: '', observations: '' })
const delai = (j: number) => (j < 0 ? `dépassé de ${-j} j` : j === 0 ? "aujourd'hui" : `dans ${j} j`)

/** Équipements de protection individuelle : ce qui a été remis à chaque salarié, et ce qu'il faut renouveler. */
export default function Epi({ peutModifier }: { peutModifier: boolean }) {
  const [salaries, setSalaries] = useState<Salarie[]>([])
  const [liste, setListe] = useState<Dotation[] | null>(null)
  const [aRenouveler, setARenouveler] = useState<Dotation[]>([])
  const [filtre, setFiltre] = useState({ search: '', salarie: '', equipement: '' })
  const [s, setS] = useState(vide)
  const [ouvert, setOuvert] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => {
    api<Page<Dotation>>(`/hse/epi/?${new URLSearchParams(filtre)}&page_size=200`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
    api<Dotation[]>('/hse/epi/renouvellements/').then(setARenouveler).catch(() => undefined)
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => { api<Salarie[]>('/hse/epi/salaries/').then(setSalaries).catch(() => undefined) }, [])

  async function remettre(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      await api('/hse/epi/', { method: 'POST', body: JSON.stringify({ ...s, salarie: Number(s.salarie), a_renouveler_le: s.a_renouveler_le || null }) })
      setS({ ...vide(), salarie: s.salarie, date_remise: s.date_remise })   // on enchaîne les équipements d'un même salarié
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  async function supprimer(d: Dotation) {
    if (!confirm(`Supprimer cette ligne (${d.equipement_libelle.toLowerCase()} remis à ${d.salarie_nom}) ?`)) return
    try {
      await api(`/hse/epi/${d.id}/`, { method: 'DELETE' })
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }
  /** Prépare la remise du même équipement au même salarié. */
  function renouveler(d: Dotation) {
    setS({ ...vide(), salarie: String(d.salarie), equipement: d.equipement, precision: d.precision, quantite: d.quantite })
    setOuvert(true)
    scrollTo({ top: 0 })
  }
  return (
    <>
      <div className="barre">
        <h2>Équipements de protection</h2>
        {peutModifier && !ouvert && <div className="actions"><button onClick={() => setOuvert(true)}>Remettre un équipement</button></div>}
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {ouvert && (
        <form onSubmit={remettre}>
          <fieldset>
            <legend>Remise d'un équipement</legend>
            {salaries.length === 0 && <p className="aide">Aucun salarié en poste : les salariés se créent dans RH, Personnel.</p>}
            <div className="grille">
              <label>Salarié<select required value={s.salarie} onChange={(e) => setS({ ...s, salarie: e.target.value })}><option value="">Choisir</option>{salaries.map((x) => <option key={x.id} value={x.id}>{x.nom} ({x.matricule}) · {x.site_nom}</option>)}</select></label>
              <label>Équipement<select value={s.equipement} onChange={(e) => setS({ ...s, equipement: e.target.value })}>{EQUIPEMENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
              <label>Modèle, taille ou pointure<input maxLength={100} value={s.precision} onChange={(e) => setS({ ...s, precision: e.target.value })} /></label>
              <label>Quantité<input type="number" min="1" max="99" required value={s.quantite} onChange={(e) => setS({ ...s, quantite: Number(e.target.value) })} /></label>
              <label>Remis le<input type="date" required max={aujourdHui()} value={s.date_remise} onChange={(e) => setS({ ...s, date_remise: e.target.value })} /></label>
              <label>À renouveler le<input type="date" min={s.date_remise} value={s.a_renouveler_le} onChange={(e) => setS({ ...s, a_renouveler_le: e.target.value })} /></label>
              <label>Observations<input maxLength={200} value={s.observations} onChange={(e) => setS({ ...s, observations: e.target.value })} /></label>
            </div>
            <div className="actions"><button disabled={enCours}>Enregistrer la remise</button><button type="button" className="secondaire" onClick={() => setOuvert(false)}>Fermer</button></div>
          </fieldset>
        </form>
      )}
      {aRenouveler.length > 0 && (
        <fieldset>
          <legend>À renouveler dans les 30 jours</legend>
          <div className="defilant"><table>
            <thead><tr><th>Salarié</th><th>Site</th><th>Équipement</th><th>Échéance</th><th></th></tr></thead>
            <tbody>{aRenouveler.map((d) => (
              <tr key={d.id}>
                <td>{d.salarie_nom} <span className="aide">{d.matricule}</span></td><td>{d.site_nom}</td><td>{d.equipement_libelle}{d.precision && <span className="aide"> · {d.precision}</span>}</td>
                <td>{dateFr(d.a_renouveler_le!)} <span className={`pastille ${d.jours! < 0 ? 'u1' : 'partielle'}`}>{delai(d.jours!)}</span></td>
                <td>{peutModifier && <button type="button" className="lien" onClick={() => renouveler(d)}>Remettre</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </fieldset>
      )}
      <div className="grille filtres large">
        <label>Recherche<input placeholder="Nom, matricule" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Salarié<select value={filtre.salarie} onChange={(e) => setFiltre({ ...filtre, salarie: e.target.value })}><option value="">Tous</option>{salaries.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}</select></label>
        <label>Équipement<select value={filtre.equipement} onChange={(e) => setFiltre({ ...filtre, equipement: e.target.value })}><option value="">Tous</option>{EQUIPEMENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucune remise enregistrée.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Remis le</th><th>Salarié</th><th>Équipement</th><th>Qté</th><th>À renouveler</th><th>Remis par</th><th></th></tr></thead>
            <tbody>
              {liste.map((d) => (
                <tr key={d.id}>
                  <td>{dateFr(d.date_remise)}</td><td>{d.salarie_nom} <span className="aide">{d.matricule}</span></td>
                  <td>{d.equipement_libelle}{d.precision && <span className="aide"> · {d.precision}</span>}{d.observations && <><br /><span className="aide">{d.observations}</span></>}</td>
                  <td>{d.quantite}</td><td>{d.a_renouveler_le ? dateFr(d.a_renouveler_le) : ''}</td><td>{d.remis_par_nom}</td>
                  <td>{peutModifier && <button type="button" className="lien" onClick={() => supprimer(d)}>Supprimer</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
