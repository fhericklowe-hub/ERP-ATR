import { useEffect, useState } from 'react'
import { api } from '../api'
import { montant } from '../achats/commandes'
import { dateFr } from '../achats/types'
import { nombre } from '../stock/types'
import type { Materiel } from './types'

type Historique = {
  nombre: number
  heures: string
  couts: { main_oeuvre: string; pieces: string; total: string } | null
  ordres: { id: number; numero: string; cree_le: string; type_libelle: string; statut_libelle: string; description: string; heures: string; cout: string | null }[]
}

/** Les ordres de réparation d'un matériel et ce qu'ils ont coûté. `seul` : affiché comme une page, avec son titre. */
export default function HistoriqueMateriel({ id, seul }: { id: number; seul?: boolean }) {
  const [h, setH] = useState<Historique | null>(null)
  const [m, setM] = useState<Materiel | null>(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Historique>(`/technique/materiels/${id}/historique/`).then(setH).catch((e: Error) => setErreur(e.message))
    if (seul) api<Materiel>(`/technique/materiels/${id}/`).then(setM).catch(() => undefined)
  }, [id, seul])

  const corps = (
    <>
      {erreur && <p className="erreur">{erreur}</p>}
      {!h && !erreur && <p>Chargement…</p>}
      {h && h.nombre === 0 && <p className="aide">Aucun ordre de réparation sur ce matériel.</p>}
      {h && h.nombre > 0 && (
        <>
          <dl>
            <dt>Ordres de réparation</dt><dd>{h.nombre}</dd>
            <dt>Temps passé</dt><dd>{nombre(h.heures)} h</dd>
            {h.couts && <><dt>Main-d'œuvre</dt><dd>{montant(h.couts.main_oeuvre)} XOF</dd><dt>Pièces</dt><dd>{montant(h.couts.pieces)} XOF</dd><dt>Coût total</dt><dd><strong>{montant(h.couts.total)} XOF</strong></dd></>}
          </dl>
          <div className="defilant">
            <table>
              <thead><tr><th>N°</th><th>Ouvert le</th><th>Travaux</th><th>État</th><th className="nombre">Heures</th>{h.couts && <th className="nombre">Coût</th>}</tr></thead>
              <tbody>
                {h.ordres.map((o) => (
                  <tr key={o.id}>
                    <td><a href={`#/ordres/${o.id}`}>{o.numero}</a></td><td>{dateFr(o.cree_le)}</td>
                    <td>{o.description}<br /><span className="aide">{o.type_libelle}</span></td><td>{o.statut_libelle}</td>
                    <td className="nombre">{Number(o.heures) ? `${nombre(o.heures)} h` : ''}</td>{h.couts && <td className="nombre">{o.cout && Number(o.cout) ? montant(o.cout) : ''}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
  if (!seul) return <fieldset><legend>Historique des réparations</legend>{corps}</fieldset>
  return (
    <div className="fiche">
      <p><a href="#/parc">← Parc de matériels</a></p>
      <h2>{m ? `${m.code} · ${m.designation}` : 'Matériel'}</h2>
      {m && <p className="aide">{[m.type_libelle, m.marque, m.modele, m.immatriculation, m.site_nom, m.etat_libelle, m.compteur_heures && `${nombre(m.compteur_heures)} h`, m.compteur_km && `${nombre(m.compteur_km)} km`].filter(Boolean).join(' · ')}</p>}
      <h3>Historique des réparations</h3>
      {corps}
      <div className="actions"><a className="bouton secondaire" href={`#/ordres/nouveau?materiel=${id}`}>Ouvrir un OR</a></div>
    </div>
  )
}
