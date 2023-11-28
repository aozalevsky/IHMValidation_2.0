###################################
# Script :
# 1) Contains class for plots that
# combines infromation from multiple
# datasets
#
# ganesans - Salilab - UCSF
# ganesans@salilab.org
###################################
import os
import utility
from mmcif_io import GetInputInformation
import bokeh
import numpy as np
from bokeh.io import output_file, curdoc, export_png, export_svg, show
from bokeh.models import (ColumnDataSource, Legend, LegendItem, FactorRange,
                          Div, BasicTickFormatter)
from bokeh.palettes import viridis, Reds256, linear_palette
from bokeh.plotting import figure, save
from bokeh.models.widgets import Tabs, Panel
from bokeh.layouts import row
from bokeh.core.validation import silence
from bokeh.core.validation.warnings import MISSING_RENDERERS, EMPTY_LAYOUT
from bokeh.transform import factor_cmap
from bokeh.layouts import gridplot, column
silence(MISSING_RENDERERS, True)
silence(EMPTY_LAYOUT, True)



class Plots(GetInputInformation):
    def __init__(self, mmcif, imageDirName, driver):
        super().__init__(mmcif)
        self.ID = str(GetInputInformation.get_id(self))
        self.dirname = os.path.dirname(os.path.abspath(__file__))
        self.imageDirName = imageDirName
        self.filename = os.path.join(self.imageDirName)
        self.driver=driver

    def plot_quality_at_glance(self, molprobity_data: dict, exv_data: dict,
                               sas_data: dict, sas_fit: dict, cx_fit: dict) -> bokeh.plotting.figure:

        # create tabs list to add all the panel figures (model quality, data quality.. etc)
        output_file(self.ID+"quality_at_glance.html", mode="inline")

        # MODEL QUALITY
        # check for molprobity or excluded volume data
        if molprobity_data:
            # if molprobity data, plot that
            # every model has clashscore, rama outliers, and rota outliers
            Models = molprobity_data['Names']
            Scores = ['Clashscore', 'Ramachandran outliers',
                      'Sidechain outliers']
            data = {'models': Models,
                    'Clashscore': molprobity_data['Clashscore'],
                    'Ramachandran outliers': molprobity_data['Ramachandran outliers'],
                    'Sidechain outliers': molprobity_data['Sidechain outliers']}
            y = [(model, score) for model in Models for score in Scores]
            counts = sum(zip(data['Clashscore'], data['Ramachandran outliers'],
                         data['Sidechain outliers']), ())
            source = ColumnDataSource(data=dict(y=y, counts=counts))

            # if there are more than 7 models, we will increase the size of the plots
            # this is important, else the plots look ugly

            plots = []

            # get data ranges
            lower, upper = utility.calc_optimal_range(counts)

            # create plot
            for i, name_ in enumerate(molprobity_data['Names']):

                p = figure(
                    y_range=FactorRange(*y[i * 3: (i + 1) * 3]),
                    # Force left limit at zero
                    x_range=(0, upper),
                    plot_height=120,
                    plot_width=700
                )

                p.hbar(y=source.data['y'][i * 3: (i + 1) * 3],
                       right=source.data['counts'][i * 3: (i + 1) * 3],
                       width=0.9, line_color="white",
                       fill_color=factor_cmap('y', palette=viridis(len(Scores)),
                                              factors=Scores,
                                              start=1, end=2)
                       )
                # set labels and fonts
                p.xaxis.major_label_text_font_size = "12pt"
                p.yaxis.major_label_text_font_size = "12pt"
                p.xaxis.axis_label = 'Outliers'
                p.xaxis.axis_label_text_font_style = 'italic'
                p.left[0].group_text_font_size = '14px'
                p.left[0].group_label_orientation = 'horizontal'
                p.title.vertical_align = 'top'
                p.title.align = "center"
                p.output_backend = "svg"
                plots.append(p)

                export_svg(p, filename=self.filename+'/' +
                            self.ID+'_' + str(i) + "_quality_at_glance_MQ.svg", webdriver=self.driver)

            grid = gridplot(plots, ncols=1,
                            merge_tools=True,
                            toolbar_location='right')
            grid.children[1].css_classes = ['scrollable']
            grid.children[1].sizing_mode = 'fixed'
            grid.children[1].height = 450
            grid.children[1].width = 800

            title = Div(text="<p>Model Quality: Molprobity Analysis</p>",
                        style={"font-size": "1.5em", "font-weight": "bold",
                               "text-align": "center", "width": '100%'}, width=800
                        )

            fullplot = column(title, grid)

        # if there isn't molprobity data, we plot exc vol data
        elif exv_data:
            model = exv_data['Models']
            satisfaction = exv_data['Number of violations']
            # make sure data is plot-able
            try:
                counts = [float(i) for i in satisfaction]
            except (ValueError):
                return
            violations = exv_data['Excluded Volume Satisfaction (%)']
            Scores = ['Model ' + str(i+1) for i, j in enumerate(model)]
            legends = ['Model ' + str(i+1) + ': ' + str(int(j)) +
                       '('+str(violations[i])+' %)' for i, j in enumerate(counts)]

            # set the size of the axis
            n = 3 if len(model) < 3 else len(model)
            source = ColumnDataSource(
                data=dict(Scores=Scores, counts=counts, legends=legends, color=viridis(n)))

            #  build plots
            plots = []

            # get ranges
            lower, upper = utility.calc_optimal_range(counts)

            for i, name_ in enumerate(model):
                p = figure(y_range=source.data['Scores'][i: i + 1], x_range=(lower, upper), plot_height=100,
                           plot_width=700)  # , title='Model Quality: Excluded Volume Analysis')
                # p.xaxis.formatter = BasicTickFormatter(use_scientific=True, power_limit_high=3)
                p.xaxis.ticker.desired_num_ticks = 3

                r = p.hbar(y=source.data['Scores'][i:i + 1], right=source.data['counts'][i: i + 1], color=source.data['color'][i:i + 1], height=0.5,
                           alpha=0.8, line_color='black')
                p.xaxis.axis_label = 'Number of violations'
                legend = Legend(items=[LegendItem(label=legends[i:i + 1][j], renderers=[
                    r], index=j) for j in range(len(legends[i:i + 1]))], location='center',
                    label_text_font_size='12px', orientation='vertical')
                p.add_layout(legend, 'right')
                p.xaxis.major_label_text_font_size = "12pt"
                p.yaxis.major_label_text_font_size = "12pt"
                p.title.vertical_align = 'top'
                p.title.align = "center"
                p.output_backend = "svg"
                plots.append(p)

                export_svg(p, filename=self.filename+'/' +
                            self.ID+'_' + str(i) + "_quality_at_glance_MQ.svg", webdriver=self.driver)

            grid = gridplot(plots, ncols=1,
                            merge_tools=True,
                            toolbar_location='right')
            grid.children[1].css_classes = ['scrollable']
            grid.children[1].sizing_mode = 'fixed'
            grid.children[1].height = 450
            grid.children[1].width = 800

            title = Div(text='<p>Model Quality: Excluded Volume Analysis</p>',
                        style={"font-size": "1.5em", "font-weight": "bold",
                               "text-align": "center", "width": '100%'}, width=800
                        )

            fullplot = column(title, grid)

        # if neither exc vol nor molp data exists, we create a blank plot
        # pdb-dev visuals keep changing, so this plot might or might not make sense
        # we are keeping it, just in case the visuals change again
        else:
            Scores = ['']
            counts = ['']
            legends = ['']
            source = ColumnDataSource(
                data=dict(Scores=Scores, counts=counts, legends=legends))
            p = figure(y_range=Scores, x_range=(0, 1),
                       plot_height=300, plot_width=800)

            p.ygrid.grid_line_color = None
            p.xaxis.axis_label_text_font_size = "14pt"
            p.yaxis.axis_label_text_font_size = "14pt"
            p.title.text_font_size = '14pt'
            p.title.align = "center"

            p.output_backend = "svg"
            p.title.vertical_align = 'top'
            fullplot = p
        # make panel figures
        # first panel is model quality
        export_svg(fullplot, filename=self.filename+'/' +
                    self.ID+"quality_at_glance_MQ.svg", webdriver=self.driver)
        export_png(fullplot, filename=self.filename+'/' +
                   self.ID+"quality_at_glance_MQ.png", webdriver=self.driver)
        save(fullplot, filename=self.filename+'/' +
             self.ID+"quality_at_glance_MQ.html")
        # DATA QUALITY
        # check for sas data, if exists, plot
        # this section will be updated with more data assessments, as and when it is complete
        if len(sas_data.keys()) > 0:
            Rgl = {0: 'P(r)', 1: 'Guinier'}
            Scores = [Rgl[m] + ' ('+i+')' for i, j in sas_data.items()
                      for m, n in enumerate(j)]
            counts = [float(n)for i, j in sas_data.items()
                      for m, n in enumerate(j)]
            legends = [str(i)+' nm' for i in counts]
            source = ColumnDataSource(data=dict(
                Scores=Scores, counts=counts, legends=legends, color=viridis(len(legends))))
            pd = figure(y_range=Scores, x_range=(0, max(
                counts)+1), plot_height=450, plot_width=800, title="Data Quality for SAS: Rg Analysis",)
            rd = pd.hbar(y='Scores', right='counts', color='color', height=0.5,
                         source=source, alpha=0.8, line_color='black')
            pd.ygrid.grid_line_color = None
            pd.xaxis.axis_label = 'Distance (nm)'
            pd.xaxis.major_label_text_font_size = "12pt"
            pd.yaxis.major_label_text_font_size = "12pt"
            pd.title.text_font_size = '14pt'
            legend = Legend(items=[LegendItem(label=legends[i], renderers=[
                            rd], index=i) for i in range(len(legends))], location='center',
                            orientation='vertical', label_text_font_size="12px")
            pd.add_layout(legend, 'right')
            pd.legend.label_text_font_size = "12px"
            pd.xaxis.axis_label_text_font_style = 'italic'
            pd.yaxis.axis_label_text_font_style = 'italic'
            pd.xaxis.axis_label_text_font_size = "14pt"
            pd.yaxis.major_label_text_font_size = "14pt"
            pd.title.vertical_align = 'top'
            pd.title.align = "center"
            pd.output_backend = "svg"
            export_svg(pd, filename=self.filename+'/' +
                        self.ID+"quality_at_glance_DQ.svg", webdriver=self.driver)
            export_png(pd, filename=self.filename+'/' +
                       self.ID+"quality_at_glance_DQ.png", webdriver=self.driver)
            save(pd, filename=self.filename+'/' +
                 self.ID+"quality_at_glance_DQ.html")
        # FIT TO DATA QUALITY
        # check for sas data, if exists, plot
        # this section will be updated with more data assessments, as and when it is complete
        if len(sas_fit.keys()) > 0:
            Scores = [' \u03C7\u00b2 Fit ' +
                      str(int(m+1)) + ' ('+i+')' for i, j in sas_fit.items() for m, n in enumerate(j)]
            counts = [float(n) for i, j in sas_fit.items()
                      for m, n in enumerate(j)]
            legends = [str(i) for i in counts]
            source = ColumnDataSource(data=dict(
                Scores=Scores, counts=counts, legends=legends, color=viridis(len(legends))))
            pf = figure(y_range=Scores, x_range=(0, max(counts)+1), plot_height=450,
                        plot_width=800, title="Fit to SAS Data:  \u03C7\u00b2 Fit")
            rf = pf.hbar(y='Scores', right='counts', color='color', height=0.5,
                         source=source, alpha=0.8, line_color='black')
            pf.ygrid.grid_line_color = None
            pf.title.text_font_size = '14pt'
            pf.xaxis.axis_label = 'Fit value'
            pf.xaxis.major_label_text_font_size = "12pt"
            pf.yaxis.major_label_text_font_size = "12pt"
            legend = Legend(items=[LegendItem(label=legends[i], renderers=[
                            rf], index=i) for i in range(len(legends))], location="center",
                            orientation='vertical', label_text_font_size="12px")
            pf.add_layout(legend, 'right')
            pf.title.vertical_align = 'top'
            pf.title.align = "center"
            pf.output_backend = "svg"
            pf.legend.label_text_font_size = "12px"
            pf.xaxis.axis_label_text_font_style = 'italic'
            pf.yaxis.axis_label_text_font_style = 'italic'
            pf.xaxis.axis_label_text_font_size = "14pt"
            pf.yaxis.major_label_text_font_size = "14pt"
            pf.title.vertical_align = 'top'
            pf.title.align = "center"
            pf.output_backend = "svg"
            export_svg(pf, filename=self.filename+'/' +
                        self.ID+"quality_at_glance_FQ.svg", webdriver=self.driver)
            export_png(pf, filename=self.filename+'/' +
                       self.ID+"quality_at_glance_FQ.png", webdriver=self.driver)
            save(pf, filename=self.filename+'/' +
                 self.ID+"quality_at_glance_FQ.html")
        # check for XL_MS data, if exists, plot
#        if len(cx_fit.keys()) > 0:
#            Scores = ['Model '+str(i) for i, j in cx_fit.items()]
#            counts = [round(float(j), 2) for i, j in cx_fit.items()]
#            # legends=[str(i) for i in counts]
#            legends = ['Model ' + str(i+1) + ': ' +
#                       str(j)+'%' for i, j in enumerate(counts)]
#            source = ColumnDataSource(data=dict(
#                Scores=Scores, counts=counts, legends=legends, color=viridis(len(legends))))
#            pf1 = figure(y_range=Scores, x_range=(0, max(counts)+1),
#                         plot_height=450, plot_width=800, title="Fit to XL-MS Input")
#            rf1 = pf1.hbar(y='Scores', right='counts', color='color',
#                           source=source, alpha=0.8, line_color='black')
#            pf1.ygrid.grid_line_color = None
#            pf1.xaxis.major_label_text_font_size = "12pt"
#            pf1.yaxis.major_label_text_font_size = "12pt"
#            pf1.title.text_font_size = '12pt'
#            pf1.title.align = "center"
#            pf1.title.vertical_align = 'top'
#
#            legend = Legend(items=[LegendItem(label=legends[i], renderers=[
#                            rf1], index=i) for i in range(len(legends))], location='center',
#                            orientation='vertical', label_text_font_size="12px")
#            pf1.add_layout(legend, 'right')
#            pf1.output_backend = "svg"
#            export_svgs(pf1, filename=self.filename+'/' +
#                        self.ID+"quality_at_glance_FQ1.svg")
#            export_png(pf1, filename=self.filename+'/' +
#                       self.ID+"quality_at_glance_FQ1.png")
#            save(pf1, filename=self.filename+'/' +
#                 self.ID+"quality_at_glance_FQ1.html")
