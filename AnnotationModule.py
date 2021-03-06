import logging
from BaseImage import printMaskHelper
from skimage import io, img_as_ubyte
from skimage.draw import polygon
import os
from pathlib import PurePosixPath

import xml.etree.ElementTree as ET
import numpy as np

""" 
xmlMask will create a mask that is true inside the annotated region described in the specified xml file. The xml file must follow the ImageScope format, the minimal components of which are:

<?xml version="1.0" encoding="UTF-8"?>
<Annotations>
<Annotation>
<Regions>
<Region>
<Vertices>
<Vertex X="56657.4765625" Y="78147.3984375"/>
<Vertex X="56657.4765625" Y="78147.3984375"/>
<Vertex X="56664.46875" Y="78147.3984375"/>
</Region>
</Regions>
</Annotation>
</Annotations>

With more <Annotation> or <Region> blocks as needed for additional annotations. There is no functional difference between multiple <Annotation> blocks and one <Annotation> blocks with multiple <Region> blocks
"""

def get_points(xml_fname):
    """Parses the xml file to get those annotations as lists of verticies"""
    # create element tree object
    tree = ET.parse(xml_fname)

    # get root element
    root = tree.getroot()

    points = []

    for annotation in root.findall('Annotation'):
        for regions in annotation.findall('Regions'):
            for region in regions.findall('Region'):
                for vertices in region.findall('Vertices'):
                    points.append([(int(float(vertex.get('X'))),int(float(vertex.get('Y')))) for vertex in vertices.findall('Vertex')])

    return points


def resize_points(points, resize_factor):
    for k, pointSet in enumerate(points):
        points[k] = [(int(p[0] * resize_factor), int(p[1] * resize_factor)) for p in pointSet]

    return points.copy()

def mask_out_annotation(s,xml_fname):
    """Returns the mask of annotations"""

    points = get_points(xml_fname)

    resize_factor = np.shape(s["img_mask_use"])[1] / s["image_base_size"][0]

    points = resize_points(points, resize_factor)

    mask = np.zeros((np.shape(s["img_mask_use"])[0],np.shape(s["img_mask_use"])[1]),dtype=np.uint8)

    for pointSet in points:
        poly = np.asarray(pointSet)
        rr, cc = polygon(poly[:,1],poly[:,0],mask.shape)
        mask[rr,cc] = 1

    return mask

def xmlMask(s,params):
    logging.info(f"{s['filename']} - \txmlMask")
    mask = s["img_mask_use"]

    xml_basepath = params.get("xml_filepath",None)
    xml_suffix = params.get("xml_suffix", "")
    if not xml_basepath:
        xml_basepath = s["dir"]

    xml_fname = xml_basepath + os.sep + PurePosixPath(s['filename']).stem + xml_suffix + '.xml'

    logging.info(f"{s['filename']} - \tusing {xml_fname}")

    annotationMask = mask_out_annotation(s,xml_fname) > 0
    io.imsave(s["outdir"] + os.sep + s["filename"] + "_xmlMask.png", img_as_ubyte(annotationMask))

    prev_mask = s["img_mask_use"]
    s["img_mask_use"] = prev_mask & annotationMask

    s.addToPrintList("xmlMask",
                     printMaskHelper(params.get("mask_statistics", s["mask_statistics"]), prev_mask, s["img_mask_use"]))

    if len(s["img_mask_use"].nonzero()[0]) == 0:  # add warning in case the final tissue is empty
        logging.warning(
            f"{s['filename']} - After AnnotationModule.xmlMask NO tissue remains detectable! Downstream modules likely to be incorrect/fail")
        s["warnings"].append(
            f"After AnnotationModule.xmlMask NO tissue remains detectable! Downstream modules likely to be incorrect/fail")

    return