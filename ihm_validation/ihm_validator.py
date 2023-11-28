#!/usr/bin/env python
###################################
# Script to run validation and write
# to HTML and PDF
# ganesans - Salilab - UCSF
# ganesans@salilab.org
###################################
from collections import defaultdict
import os
import shutil
import datetime
import json
import argparse
from multiprocessing import Manager
import pdfkit
import jinja2
import pytz
import sys
import logging
from pathlib import Path
import utility
from report import WriteReport

# from validation.WKhtmlToPdf import  wkhtmltopdf
# import utility

####################################################################################################################
# Add input arguments for supp table
#####################################################################

parser = argparse.ArgumentParser()
parser.add_argument('-v', dest='verbose', action='store_true',
                    help="Verbose output")
parser.add_argument('-p', type=str, default='No',
                    help="Physical principles used in modeling yes/no?")
parser.add_argument('-f', default='PDBDEV_00000001.cif',
                    help="Input mmcif file")
parser.add_argument('--databases-root', type=str, default='.', required=False,
                    help="Path to a local copy of SASBDB and EMDB databases")
parser.add_argument('--cache-root', type=str,
                    default=str(Path('..', 'Validation', 'cache')),
                    required=False,
                    help="Path to a local copy of SASBDB and EMDB databases")
parser.add_argument('--nocache', action='store_true', default=False,
                    help="Ignore cached assesment results")
parser.add_argument('--output-root', type=str, default=str(Path(Path(__file__).parent.resolve(), 'Validation')),
                    help="Path to a directory where the output will be written")
parser.add_argument('--output-prefix', type=str, default=None,
                    help="Prefix of the output directory. Default is a stem of the mmCIF file")
parser.add_argument('--html-mode', type=str, default='local',
                    choices=['local', 'pdb-dev'],
                    help="HTML mode affects paths to various statis resources")
parser.add_argument('--html-resources',
                    type=str,
                    default=str(Path(Path(__file__).parent.parent.resolve(), 'static')),
                    help="Path to static HTML resources")
parser.add_argument('--keep-html', action='store_true', default=False,
                    help="Keep uncompressed HTML output")
parser.add_argument('--force', action='store_true', default=False,
                    help="Overwright output files")
parser.add_argument(
    '-ls', type=list, default=['No location specified'], help="add location of your scripts")
parser.add_argument(
    '-ld', type=list, default=['No location specified'], help="add location of your analysis files")
parser.add_argument(
    '-m', type=list, default=['Method details not available'], help="add information on your method")
parser.add_argument('-models', type=str, default='1',
                    help="number of models in an ensemble, if you have multiple ensembles, add comma-separated string")
parser.add_argument('-c', type=str, default='Distance threshold-based clustering used if ensembles are deposited',
                    help="The type of clustering algorithm used to analyze the ensemble")
parser.add_argument('-mp', type=str, default='10 &#8491 (average RMSF of the solution ensemble with respect to the centroid structure)',
                    help="add model precision. Model precision is defined as average RMSF of the solution ensemble with respect to the centroid structure")
parser.add_argument('-sv', type=list, default=['Information related to sampling validation has not been provided'],
                    help="add model precision. Model precision is defined as average RMSF of the solution ensemble with respect to the centroid structure")
parser.add_argument('-v1', type=list, default=['Fit of model to information used to compute it has not been determined'],
                    help="Add information on satisfaction of input data/restraints")
parser.add_argument('-v2', type=str, nargs='+', default=['Fit of model to information not used to compute it has not been determined'],
                    help="Add information on satisfaction of data not used for modeling")
parser.add_argument('-dv', type=list, default=[
                    'Quality of input data has not be assessed'], help="Add information on quality of input data")
parser.add_argument('-res', type=list, default=['Rigid bodies: 1 residue per bead.',
                                                'Flexible regions: N/A'], help="Add information on model quality (molprobity or excluded volume)")

args = parser.parse_args()
if args.p.upper() == 'YES':
    physics = [
        'Sequence connectivity',
        'Excluded volume'
    ]
else:
    physics = ['Information about physical principles was not provided']

logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

#############################################################################################################################
# Input for Jinja
####################################################################################
config = pdfkit.configuration()
options = {
    'page-size': 'Letter',
    'margin-top': '0.5in',
    'margin-right': '0.5in',
    'margin-bottom': '0.5in',
    'margin-left': '0.5in',
    'enable-javascript': None,
    'header-left': '[page] of [topage]',
    'footer-center': 'IM Structure Validation Report',
    'footer-line': '',
    'header-line': '',
    'footer-spacing': '5',
    'header-spacing': '5',
    "enable-local-file-access": "",
}

options_supp = {
    'page-size': 'A4',
    'margin-top': '0.75in',
    'margin-right': '0.75in',
    'margin-bottom': '0.75in',
    'margin-left': '0.75in',
    'enable-javascript': None,
    'header-left': '[page] of [topage]',
    'footer-center': 'IM Summary Table',
    'footer-line': '',
    'header-line': '',
    'footer-spacing': '5',
    'header-spacing': '5'
}

template_flask = [
    "main.html",
    "data_quality.html",
    "model_quality.html",
    "model_composition.html",
    "formodeling.html",
    "about_validation.html",
    "validation_help.html",
]

# Get the UTC time from ruser
d = pytz.utc.localize(datetime.datetime.utcnow())
# Set UCSF's timezone
timezone = pytz.timezone("America/Los_Angeles")
d_format = d.astimezone(timezone)
timestamp = d_format.strftime("%B %d, %Y - %I:%M %p %Z")


output_root = args.output_root

output_prefix = Path(args.f).stem
if args.output_prefix is not None:
    output_prefix = args.output_prefix

output_path = Path(output_root, output_prefix)

dirNames = {
    'root': str(output_path),
    'html': str(Path(output_path, f'{output_prefix}_html')),
}

dirNames.update(
    {
        'images':  str(Path(dirNames['html'], 'images')),
        'csv':  str(Path(dirNames['html'], 'csv')),
        'pdf':  str(Path(dirNames['html'], 'pdf')),
        # 'json': str(Path(output_path, 'json')),
    }
)

# This is a temporary hack for ../templates
template_path = Path(Path(__file__).parent.parent.resolve(), 'templates')
templateLoader = jinja2.FileSystemLoader(searchpath=template_path)
templateEnv = jinja2.Environment(loader=templateLoader)
template_pdf = "full_validation_pdf.html"
template_file_supp = "summary_validation_pdf.html"
Template_Dict = {}
Template_Dict['date'] = timestamp
#############################################################################################################################
# Jinja scripts
#############################################################################################################################


def createdirs(dirNames: dict):
    for name in list(dirNames.values()):
        if Path(name).is_dir():
            logging.info(f"Directory {name} already exists")
        else:
            os.mkdir(name)
            logging.info(f"Directory {name} created ")


def write_html(mmcif_file: str, template_dict: dict, template_list: list, dirName: str):
    for template_file in template_list:
        template = templateEnv.get_template(template_file)
        outputText = template.render(template_dict)

        with open(os.path.join(os.path.join(dirName, template_file)), "w") as fh:
                fh.write(outputText)


def write_pdf(mmcif_file: str, template_dict: dict, template_file: str, dirName: str, dirName_Output: str):
    template = templateEnv.get_template(template_file)
    outputText = template.render(template_dict)
    temp_html = os.path.join(dirName, utility.get_output_file_temp_html(mmcif_file))
    output_pdf = os.path.join(dirName_Output, utility.get_output_file_pdf(mmcif_file))

    with open(temp_html, "w") as fh:
        fh.write(outputText)

    pdfkit.from_file(temp_html, output_pdf, options=options)
    # os.remove(temp_html)

    return output_pdf

def write_supplementary_table(mmcif_file: str, template_dict: dict, template_file: str, dirName: str, dirName_supp: str):
    template = templateEnv.get_template(template_file)
    outputText = template.render(template_dict)
    temp_html = os.path.join(dirName, utility.get_supp_file_html(mmcif_file))
    output_pdf = os.path.join(dirName_supp, utility.get_supp_file_pdf(mmcif_file))

    with open(temp_html, "w") as fh:
        fh.write(outputText)

    pdfkit.from_file(temp_html, output_pdf, options=options_supp)
    os.remove(temp_html)

    return output_pdf


def write_json(mmcif_file: str, template_dict: dict, dirName: str, dirName_Outputs: str):
    j = json.dumps([{'Category': k, 'Itemized_List': v}
                    for k, v in template_dict.items()], indent=4)

    output_json = os.path.join(dirName_Outputs, utility.get_output_file_json(mmcif_file))

    with open(output_json, "w") as fh:
        fh.write(j)


############################################################################################################################
# Run script
#################################################

if __name__ == "__main__":
    from pyvirtualdisplay import Display
    from selenium import webdriver
    display = Display(visible=0, size=(1024, 768))
    display.start()
    driver = webdriver.Firefox()

    logging.info("Clean up and create output directories")
    utility.clean_all()

    if Path(output_path).is_dir():
        if args.force:
            logging.info(f'Overwriting output directory {output_path}')
            shutil.rmtree(output_path)
        else:
            logging.info(f'Output directory {output_path} exists. '
                         'Use --force to overwright')
            sys.exit(0)

    if not Path(args.cache_root).is_dir():
        os.makedirs(args.cache_root)
        logging.info(f'Created cache dir {args.cache_root}')

    createdirs(dirNames)
    manager = Manager()  # create only 1 mgr
    d = manager.dict()  # create only 1 dict
    report = WriteReport(args.f,
                         db=args.databases_root,
                         driver=driver,
                         cache=args.cache_root,
                         nocache=args.nocache)

    logging.info("Entry composition")
    template_dict = report.run_entry_composition(Template_Dict)

    logging.info("Model quality")
    template_dict, molprobity_dict, exv_data = report.run_model_quality(
        template_dict, csvDirName=dirNames['csv'], htmlDirName=dirNames['html'])

    logging.info("SAS validation")
    template_dict, sas_data, sas_fit = report.run_sas_validation(template_dict)

    logging.info("SAS validation plots")
    report.run_sas_validation_plots(
        template_dict, imageDirName=dirNames['images'])

    # uncomment below to run CX analysis
    logging.info("CX validation")
    template_dict, cx_data, cx_ertypes = report.run_cx_validation(template_dict)
    cx_fit = None

    logging.info("CX validation plots")
    report.run_cx_validation_plots(template_dict,
                                   imageDirName=dirNames['images'])

    logging.info("Quality at a glance")
    report.run_quality_glance(
        molprobity_dict, exv_data, sas_data, sas_fit, cx_fit, imageDirName=dirNames['images'])

    logging.info("Supplementary table")
    template_dict = report.run_supplementary_table(template_dict,
                                                   location=args.ls,
                                                   physics=physics,
                                                   method_details=args.m,
                                                   sampling_validation=None,
                                                   validation_input=args.v1,
                                                   cross_validation=args.v2,
                                                   Data_quality=args.dv,
                                                   clustering=None,
                                                   )
    output_pdf = write_supplementary_table(
        args.f, template_dict, template_file_supp, dirNames['pdf'], dirNames['pdf'])
    shutil.copy(output_pdf, str(output_path))

    # logging.info("Write JSON")
    # write_json(args.f, template_dict, dirNames['json'], dirNames['json'])

    logging.info("Write HTML")
    # set html mode
    template_dict['html_mode'] = args.html_mode
    write_html(args.f, template_dict, template_flask, dirNames['html'])
    if args.html_mode == 'local':
        shutil.copytree(
            args.html_resources,
            str(Path(dirNames['html'], Path(args.html_resources).stem))
        )
    # Compress html output to one file
    shutil.make_archive(
        base_name=dirNames['html'],
        root_dir=output_path,
        format='gztar')

    logging.info("Write PDF")
    output_pdf = write_pdf(args.f, template_dict, template_pdf,
              dirNames['pdf'], dirNames['pdf'])

    shutil.copy(output_pdf, str(output_path))

    # Keep uncompressed html output for convience
    # otherwise delete
    if args.keep_html:
        pass
    else:
        shutil.rmtree(dirNames['html'])

    logging.info("Final cleanup")
    utility.clean_all()
