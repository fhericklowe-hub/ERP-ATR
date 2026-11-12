import { type FormEvent, useEffect, useState } from 'react'
import { api, ouvrirFichier, type Page, type Service } from '../api'
import PiecesJointes from '../PiecesJointes'
import { dateFr, dateHeureFr } from '../achats/types'
import { type EtatStock, type LigneStock, type Magasin, type Sortie, nombre } from './types'

type Personne = { id: number; first_name: string; last_name: string; username: string }
type LigneSaisie = { article: string; quantite: string }

export function ListeSorties({ peutSortir }: { peutSortir: boolean }) {
  const [sorties, setSorties] = useState<Sortie[] | null>(null)
  const [recherche, setRecherche] = useState('')
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    const t = setTimeout(() => {
      api<Page<Sortie>>(`/stock/sorties/?search=${encodeURIComponent(recherche)}`).then((p) => setSorties(p.results)).catch((e: Error) => setErreur(e.message))
    }, 200)
    return () => clearTimeout(t)
  }, [recherche])

  return (
    <>
      <div className="barre">
        <h2>Bons de sortie</h2>
        <div className="actions">
          <a className="bouton secondaire" href="#/stock">Stock</a>
          {peutSortir && <a className="bouton" href="#/stock/sorties/nouvelle">Sortir des pièces</a>}
        </div>
      </div>
      <label className="filtre">Recherche
        <input value={recherche} placeholder="N° de bon, OR, matériel, article" onChange={(e) => setRecherche(e.target.value)} />
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!sorties && !erreur && <p>Chargement…</p>}
      {sorties?.length === 0 && <p>Aucun bon de sortie.</p>}
      {sorties && sorties.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Date</th><th>OR</th><th>Matériel</th><th>Magasin</th><th>Remis à</th><th>Pièces</th></tr></thead>
            <tbody>
              {sorties.map((s) => (
                <tr key={s.id}>
                  <td><a href={`#/stock/sorties/${s.id}`}>{s.numero}</a>{s.statut === 'ANNULE' && <> <span className="pastille">Annulé</span></>}</td>
                  <td>{dateFr(s.date)}</td>
                  <td>{s.numero_or}</td>
                  <td>{s.materiel}</td>
                  <td>{s.magasin_nom}</td>
                  <td>{s.remis_a_nom}</td>
                  <td>{s.lignes.map((l) => `${nombre(l.quantite)} ${l.designation}`).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireSortie() {
  const [magasins, setMagasins] = useState<Magasin[]>([])
  const [personnes, setPersonnes] = useState<Personne[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [stock, setStock] = useState<LigneStock[]>([])
  const [d, setD] = useState({ magasin: '', numero_or: '', materiel: '', remis_a: '', service: '', observations: '' })
  const [lignes, setLignes] = useState<LigneSaisie[]>([{ article: '', quantite: '' }])
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api<Page<Magasin>>('/emplacements/?type=SITE&actif=true').then((p) => setMagasins(p.results)).catch(() => undefined)
    api<Page<Personne>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setPersonnes(p.results)).catch(() => undefined)
    api<Page<Service>>('/services/?actif=true').then((p) => setServices(p.results)).catch(() => undefined)
  }, [])
  useEffect(() => {
    if (!d.magasin) return setStock([])
    api<EtatStock>(`/stock/etat/?magasin=${d.magasin}`).then((e) => setStock(e.results.filter((l) => Number(l.quantite) > 0))).catch(() => setStock([]))
  }, [d.magasin])

  const champ = (k: keyof typeof d, v: string) => setD((x) => ({ ...x, [k]: v }))
  const ligne = (i: number, k: keyof LigneSaisie, v: string) => setLignes((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)))
  const enStock = (article: string) => stock.find((l) => String(l.article) === article)

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const r = await api<Sortie>('/stock/sorties/', {
        method: 'POST',
        body: JSON.stringify({ ...d, service: d.service || null, lignes: lignes.filter((l) => l.article) }),
      })
      location.hash = `#/stock/sorties/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <h2>Sortir des pièces du stock</h2>
      <fieldset>
        <legend>Pour quel travail</legend>
        <div className="grille">
          <label>N° d'OR (obligatoire)
            <input required value={d.numero_or} maxLength={40} onChange={(e) => champ('numero_or', e.target.value)} />
          </label>
          <label>Matériel concerné
            <input value={d.materiel} placeholder="Engin, véhicule, immatriculation" onChange={(e) => champ('materiel', e.target.value)} />
          </label>
          <label>Magasin
            <select required value={d.magasin} onChange={(e) => { champ('magasin', e.target.value); setLignes([{ article: '', quantite: '' }]) }}>
              <option value="">Choisir…</option>
              {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
            </select>
          </label>
          <label>Remis à
            <select required value={d.remis_a} onChange={(e) => champ('remis_a', e.target.value)}>
              <option value="">Choisir…</option>
              {personnes.map((p) => <option key={p.id} value={p.id}>{`${p.first_name} ${p.last_name}`.trim() || p.username}</option>)}
            </select>
          </label>
          <label>Service
            <select value={d.service} onChange={(e) => champ('service', e.target.value)}>
              <option value="">Aucun</option>
              {services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
        </div>
      </fieldset>
      <fieldset>
        <legend>Pièces</legend>
        {d.magasin && stock.length === 0 && <p className="aide">Aucun article en stock dans ce magasin.</p>}
        {lignes.map((l, i) => (
          <div className="ligne sortie" key={i}>
            <label>Article
              <select required value={l.article} disabled={!d.magasin} onChange={(e) => ligne(i, 'article', e.target.value)}>
                <option value="">{d.magasin ? 'Choisir…' : "Choisir d'abord le magasin"}</option>
                {stock.filter((s) => String(s.article) === l.article || !lignes.some((x) => x.article === String(s.article))).map((s) => (
                  <option key={s.article} value={s.article}>{s.code} · {s.designation} ({nombre(s.quantite)} {s.unite} en stock)</option>
                ))}
              </select>
            </label>
            <label>Quantité
              <input type="number" required min="0.01" step="0.01" max={enStock(l.article)?.quantite} value={l.quantite} onChange={(e) => ligne(i, 'quantite', e.target.value)} />
            </label>
            {lignes.length > 1 && <button type="button" className="discret" onClick={() => setLignes(lignes.filter((_, j) => j !== i))}>Retirer</button>}
          </div>
        ))}
        <div className="actions">
          <button type="button" className="secondaire" onClick={() => setLignes([...lignes, { article: '', quantite: '' }])}>Ajouter une pièce</button>
        </div>
        <label>Observations<textarea value={d.observations} onChange={(e) => champ('observations', e.target.value)} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer la sortie'}</button>
        <a href="#/stock/sorties">Annuler</a>
      </div>
      <p className="aide">Une sortie enregistrée ne se modifie pas. En cas d'erreur, le responsable du stock l'annule et les pièces reviennent en stock.</p>
    </form>
  )
}

export function DetailSortie({ id }: { id: number }) {
  const [s, setS] = useState<Sortie | null>(null)
  const [motif, setMotif] = useState('')
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Sortie>(`/stock/sorties/${id}/`).then(setS).catch((e: Error) => setErreur(e.message))
  }, [id])

  async function annuler() {
    setErreur('')
    try {
      setS(await api<Sortie>(`/stock/sorties/${id}/annuler/`, { method: 'POST', body: JSON.stringify({ commentaire: motif }) }))
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  if (!s) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  return (
    <div className="fiche">
      <p><a href="#/stock/sorties">← Bons de sortie</a></p>
      <div className="barre">
        <h2>{s.numero}</h2>
        <button className="secondaire" onClick={() => ouvrirFichier(`/stock/sorties/${id}/pdf/`).catch((e: Error) => setErreur(e.message))}>Imprimer (PDF)</button>
      </div>
      <p className="statut">{s.statut_libelle}</p>
      <dl>
        <dt>N° d'OR</dt><dd><strong>{s.numero_or}</strong></dd>
        {s.materiel && <><dt>Matériel</dt><dd>{s.materiel}</dd></>}
        <dt>Magasin</dt><dd>{s.magasin_nom}</dd>
        <dt>Date</dt><dd>{dateFr(s.date)}</dd>
        <dt>Remis à</dt><dd>{s.remis_a_nom}{s.service_nom && ` · ${s.service_nom}`}</dd>
        <dt>Magasinier</dt><dd>{s.magasinier_nom}</dd>
        {s.observations && <><dt>Observations</dt><dd>{s.observations}</dd></>}
        {s.statut === 'ANNULE' && <><dt>Annulation</dt><dd>{s.motif_annulation} ({s.annule_par_nom}, le {dateHeureFr(s.annule_le ?? '')})</dd></>}
      </dl>
      <div className="defilant">
        <table>
          <thead><tr><th>Code</th><th>Désignation</th><th className="nombre">Quantité</th></tr></thead>
          <tbody>
            {s.lignes.map((l) => <tr key={l.id}><td>{l.code}</td><td>{l.designation}</td><td className="nombre">{nombre(l.quantite)} {l.unite}</td></tr>)}
          </tbody>
        </table>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {s.peut_annuler && (
        <fieldset>
          <legend>Annulation</legend>
          <label>Motif de l'annulation
            <textarea value={motif} onChange={(e) => setMotif(e.target.value)} />
          </label>
          <div className="actions"><button className="danger" onClick={annuler}>Annuler le bon : les pièces reviennent en stock</button></div>
        </fieldset>
      )}
      <PiecesJointes modele="stock.bonsortie" objet={id} />
    </div>
  )
}
