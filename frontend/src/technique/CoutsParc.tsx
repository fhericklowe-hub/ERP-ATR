import { useEffect, useState } from 'react'
import { api, type Page, type Site } from '../api'
import BoutonExcel from '../BoutonExcel'
import { montant } from '../achats/commandes'
import { TYPES_MATERIEL } from './types'

type Ligne = { id: number; code: string; designation: string; type_libelle: string; site_nom: string; annee: number | null; etat_libelle: string; ordres: number; heures: string; main_oeuvre: string; pieces: string; total: string }
type Resultat = { lignes: Ligne[]; total: { ordres: number; heures: string; main_oeuvre: string; pieces: string; total: string } }

const jour = (d: Date) => d.toLocaleDateString('fr-CA')

/** Les équipements qui ont coûté le plus cher en réparation sur la période. */
export default function CoutsParc() {
  const [filtre, setFiltre] = useState({ debut: `${new Date().getFullYear()}-01-01`, fin: jour(new Date()), site: '', type: '' })
  const [sites, setSites] = useState<Site[]>([])
  const [res, setRes] = useState<Resultat | null>(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => { api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined) }, [])
  useEffect(() => {
    const q = new URLSearchParams(Object.entries(filtre).filter(([, v]) => v !== ''))
    api<Resultat>(`/technique/couts-parc/?${q}`).then((r) => { setRes(r); setErreur('') }).catch((e: Error) => { setRes(null); setErreur(e.message) })
  }, [filtre])
  const maj = (c: string, v: string) => setFiltre({ ...filtre, [c]: v })
  return (
    <>
      <div className="barre">
        <h2>Coûts de réparation par équipement</h2>
        <BoutonExcel chemin="/technique/couts-parc/" filtres={filtre} nom="couts-parc" onErreur={setErreur} />
      </div>
      <p className="aide">
        Ordres de réparation ouverts pendant la période (hors annulés) : main-d'œuvre au taux horaire de l'atelier et pièces sorties du stock,
        comme sur chaque ordre. Les équipements les plus coûteux sont en tête, pour aider à décider d'une réforme ou d'un remplacement.
      </p>
      <div className="grille filtres large">
        <label>Du<input type="date" value={filtre.debut} onChange={(e) => maj('debut', e.target.value)} /></label>
        <label>Au<input type="date" value={filtre.fin} onChange={(e) => maj('fin', e.target.value)} /></label>
        <label>Site<select value={filtre.site} onChange={(e) => maj('site', e.target.value)}><option value="">Tous</option>{sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select></label>
        <label>Type<select value={filtre.type} onChange={(e) => maj('type', e.target.value)}><option value="">Tous</option>{TYPES_MATERIEL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {!res && !erreur && <p>Calcul…</p>}
      {res && res.lignes.length === 0 && <p className="aide">Aucun ordre de réparation sur cette période.</p>}
      {res && res.lignes.length > 0 && (
        <>
          <p className="chiffre-cle"><strong>{montant(res.total.total)}</strong> sur {res.total.ordres} ordre(s) et {res.lignes.length} équipement(s)</p>
          <div className="defilant">
            <table>
              <thead><tr><th>N° de parc</th><th>Équipement</th><th>Site</th><th className="nombre">Ordres</th><th className="nombre">Heures</th><th className="nombre">Main-d'œuvre</th><th className="nombre">Pièces</th><th className="nombre">Total</th></tr></thead>
              <tbody>
                {res.lignes.map((l) => (
                  <tr key={l.id}>
                    <td><a href={`#/parc/${l.id}`}>{l.code}</a></td>
                    <td>{l.designation}<br /><span className="aide">{l.type_libelle}{l.annee ? ` · ${l.annee}` : ''} · {l.etat_libelle}</span></td>
                    <td>{l.site_nom}</td><td className="nombre">{l.ordres}</td><td className="nombre">{l.heures}</td>
                    <td className="nombre">{montant(l.main_oeuvre)}</td><td className="nombre">{montant(l.pieces)}</td><td className="nombre"><strong>{montant(l.total)}</strong></td>
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
