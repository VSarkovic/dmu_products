#! env python3
# -*- coding: utf-8 -*-

import click
import numpy as np

from astropy import coordinates as coord
from astropy import units as u
from astropy.table import Column, Table
import pyvo as vo


def add_gaia_star_flag(catalogue, gaia_cat):
    """Add a flag indicating the probability of the object being as star

    This flag is based on the Gaia positions:
    - 1 if the object is possibly a star (the nearest Gaia source is between
      1.5 arcsec and 2 arcsec).
    - 2 if the object is probably a star (the nearest Gaia source is between
      0.6 arcsec and 1.5 arcsec).
    - 3 if the object is definitely a star (the nearest Gaia source is nearer
      than 0.6 arcsec).
    - 0 otherwise (the nearest Gaia source is farer than 2 arcsec).


    Parameters
    ----------
    catalogue : astropy.table.Table
        The catalogue as an astropy table. The positions must be in the ra and
        dec columns, and be expressed in degrees in the J2000 reference.
    gaia_cat : astropy.table.Table
        Gaia catalogue from HELP database.

    Returns
    -------
    astropy.table.Table
        The catalogue with a new gaia_flag column added.


    """

    flag = np.full(len(catalogue), 0, dtype=int)

    # Star positions
    star_ra = np.array(gaia_cat['ra'])
    star_dec = np.array(gaia_cat['dec'])
    star_pmra = np.array(gaia_cat['pmra'])
    star_pmdec = np.array(gaia_cat['pmdec'])

    # The proper motion is not available everywhere. We set it to 0 where it's
    # not available.
    star_pmra[np.isnan(star_pmra)] = 0.0
    star_pmdec[np.isnan(star_pmdec)] = 0.0

    # Correct star positions with proper motion. Gaia gives positions at epoch
    # 2015 while the catalogue positions are J2000.
    star_ra += star_pmra / 1000. / 3600. * (2000-2015) * \
        np.cos(np.deg2rad(np.array(star_dec)))
    star_dec += star_pmdec / 1000. / 36000. * (2000-2015)

    # Star and master list positions
    star_pos = coord.SkyCoord(star_ra * u.degree, star_dec * u.degree)
    catalogue_pos = coord.SkyCoord(catalogue['ra'], catalogue['dec'])

    # Get all the catalogue sources within 2 arcsec of a starc
    idx_galaxy, idx_star, d2d, _ = star_pos.search_around_sky(
        catalogue_pos, 2 * u.arcsec)

    # All these sources are possible stars.
    flag[idx_galaxy] = 1

    # Those that are nearer the 1.5 arcsec are probable stars.
    flag[idx_galaxy[d2d <= 1.5 * u.arcsec]] = 2

    # Those that are nearer the 0.6 arcsec are definitely stars.
    flag[idx_galaxy[d2d <= .6 * u.arcsec]] = 3

    catalogue.add_column(Column(flag, 'gaia_flag'))

    return catalogue


@click.command()
@click.argument("catalogue", metavar="<catalogue>")
@click.argument("gaia_cat_or_field", metavar="<gaia_cat_or_field>")
def command(catalogue, gaia_cat_or_field):
    """Add gaia_flag to a catalogue

    <catalogue> is the file containing the catalogue to flag.
    <gaia_cat_or_field> is either the name of the file containing the Gaia
    catalogue or the name of a HELP field, in that case the Gaia catalogue will
    be downloaded from the HELP VO server.

    """

    try:
        gaia_cat = Table.read(gaia_cat_or_field)
    except FileNotFoundError:
        # Get the Gaia catalogue from HELP VO server
        gaia_cat = vo.tablesearch(
            "http://vohedamtest.lam.fr/__system__/tap/run/tap",
            "select top 100000000 ra,pmra,dec,pmdec from gaia.main where " \
            "field = '{}'".format(gaia_cat_or_field)
        ).table


    updated_catalogue = add_gaia_star_flag(Table.read(catalogue), gaia_cat)
    updated_catalogue.write("{}_flagged.fits".format(catalogue[:-5]))

if __name__ == "__main__":
    command()
