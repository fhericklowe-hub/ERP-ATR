import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Service } from '../api'
import BoutonExcel from '../BoutonExcel'
import { montant } from './commandes'

type Ligne = { id: number; exercice: number; service: number; service_nom: string; intitule: string; compte: number | null; compte_libelle: string; montant: string; actif: boolean; engage: string; disponible: string; en_cours: string }
type Compte = { id: number; numero: string; libelle: string }

const annee = new Date().getFullYear()
const VIDE = { id: 0, service: '', intitule: '', compte: '', montant: '', actif: true }
const somme = (lignes: Ligne[], c: 'montant' | 'engage' | 'en_cours' | 'disponible') => lignes.reduce((t, l) => t + Number(l[c]), 0)

function Jauge({ ligne }: { ligne: { montant: number; engage: number; en_cours: number } }) {
  const pct = (v: number) => (ligne.montant > 0 ? Math.min(100, (v / ligne.montant) * 100) : v > 0 ? 100 : 0)
  const engage = pct(ligne.engage)
  const total = ligne.montant > 0 ? ((ligne.engage + ligne.en_cours) / ligne.montant) * 100 : 0
  return (
    <>
      <span className="jauge" role="img" aria-label={`${Math.round(engage)} % engagé`}>
        <span style={{ width: `${engage}%` }} className={total > 100 ? 'faible' : total > 85 ? 'moyen' : ''} />
      </span>
      {Math.round(engage)} %
    </>
  )
}

/** Budget de l'exercice par service : prévu, engagé par les demandes validées, en cours de validation, disponible. */
export default function SuiviBudget({ peutModifier }: { peutModifier: boolean }) {
  const [filtre, setFiltre] = useState({ exercice: String(annee), service: '' })
  const [lignes, setLignes] = useState<Ligne[] | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [comptes, setComptes] = useState<Compte[]>([])
  const [f, setF] = useState<typeof VIDE | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => {
    const q = new URLSearchParams(Object.entries(filtre).filter(([, v]) => v !== ''))
    api<Ligne[]>(`/achats/lignes-budgetaires/?${q}`).then((l) => { setLignes(l); setErreur('') }).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Service>>('/services/?actif=true&page_size=200').then((p) => setServices(p.results)).catch(() => undefined)
    api<Compte[]>('/comptes-charge/?actif=true').then(setComptes).catch(() => undefined)
  }, [])
  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!f) return
    setEnCours(true)
    setErreur('')
    try {
      const corps = JSON.stringify({ exercice: Number(filtre.exercice), service: f.service, intitule: f.intitule, compte: f.compte || null, montant: f.montant, actif: f.actif })
      await api(f.id ? `/achats/lignes-budgetaires/${f.id}/` : '/achats/lignes-budgetaires/', { method: f.id ? 'PATCH' : 'POST', body: corps })
      setF(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  const actives = (lignes ?? []).filter((l) => l.actif)
  const total = { montant: somme(actives, 'montant'), engage: somme(actives, 'engage'), en_cours: somme(actives, 'en_cours'), disponible: somme(actives, 'disponible') }
  return (
    <>
      <div className="barre">
        <h2>Suivi du budget</h2>
        <div className="actions">
          <BoutonExcel chemin="/achats/lignes-budgetaires/" filtres={filtre} nom="suivi-budget" onErreur={setErreur} />
          {peutModifier && !f && <button onClick={() => setF({ ...VIDE, service: filtre.service })}>Nouvelle ligne</button>}
        </div>
      </div>
      <p className="aide">
        Engagé : demandes liées au budget validées sur la ligne. En cours : demandes encore dans le circuit de validation. Disponible : budget moins engagé.
      </p>
      <div className="grille filtres">
        <label>Exercice<input type="number" min="2020" max="2100" value={filtre.exercice} onChange={(e) => setFiltre({ ...filtre, exercice: e.target.value })} /></label>
        <label>Service<select value={filtre.service} onChange={(e) => setFiltre({ ...filtre, service: e.target.value })}><option value="">Tous</option>{services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select></label>
      </div>
      {f && (
        <form className="fiche" onSubmit={enregistrer}>
          <fieldset>
            <legend>{f.id ? 'Modifier la ligne' : `Nouvelle ligne ${filtre.exercice}`}</legend>
            <div className="grille">
              <label>Service<select required value={f.service} onChange={(e) => setF({ ...f, service: e.target.value })}><option value="">Choisir…</option>{services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select></label>
              <label>Intitulé<input required maxLength={150} value={f.intitule} onChange={(e) => setF({ ...f, intitule: e.target.value })} /></label>
              <label>Compte<select value={f.compte} onChange={(e) => setF({ ...f, compte: e.target.value })}><option value="">Non précisé</option>{comptes.map((c) => <option key={c.id} value={c.id}>{c.numero} · {c.libelle}</option>)}</select></label>
              <label>Montant du budget (XOF)<input type="number" required min="0" step="1" value={f.montant} onChange={(e) => setF({ ...f, montant: e.target.value })} /></label>
            </div>
            <label className="case"><input type="checkbox" checked={f.actif} onChange={(e) => setF({ ...f, actif: e.target.checked })} />Ligne active (proposée dans les demandes)</label>
            <div className="actions"><button disabled={enCours}>Enregistrer</button><button type="button" className="secondaire" onClick={() => setF(null)}>Fermer</button></div>
          </fieldset>
        </form>
      )}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {!lignes && !erreur && <p>Chargement…</p>}
      {lignes?.length === 0 && <p className="aide">Aucune ligne budgétaire pour cet exercice.{peutModifier && ' Créez-les avec « Nouvelle ligne ».'}</p>}
      {lignes && lignes.length > 0 && (
        <>
          <p className="chiffre-cle"><strong>{montant(total.disponible)}</strong> disponibles sur {montant(total.montant)} de budget <span className="aide">· {montant(total.engage)} engagés · {montant(total.en_cours)} en cours de validation</span></p>
          <div className="defilant">
            <table>
              <thead><tr><th>Service</th><th>Ligne</th><th className="nombre">Budget</th><th className="nombre">Engagé</th><th className="nombre">En cours</th><th className="nombre">Disponible</th><th>Consommé</th>{peutModifier && <th></th>}</tr></thead>
              <tbody>
                {lignes.map((l) => (
                  <tr key={l.id} style={l.actif ? undefined : { opacity: 0.55 }}>
                    <td>{l.service_nom}</td>
                    <td>{l.intitule}{!l.actif && ' (inactive)'}{l.compte_libelle && <><br /><span className="aide">{l.compte_libelle}</span></>}</td>
                    <td className="nombre">{montant(l.montant)}</td><td className="nombre">{montant(l.engage)}</td><td className="nombre">{Number(l.en_cours) ? montant(l.en_cours) : ''}</td>
                    <td className={`nombre${Number(l.disponible) < 0 ? ' erreur' : ''}`}><strong>{montant(l.disponible)}</strong></td>
                    <td><Jauge ligne={{ montant: Number(l.montant), engage: Number(l.engage), en_cours: Number(l.en_cours) }} /></td>
                    {peutModifier && <td><button className="secondaire" onClick={() => setF({ id: l.id, service: String(l.service), intitule: l.intitule, compte: l.compte ? String(l.compte) : '', montant: String(Number(l.montant)), actif: l.actif })}>Modifier</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
