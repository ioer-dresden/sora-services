import arcpy
import json
import requests
import os

'''
Task Respository for the REST-Service cooridinates (https://edn.ioer.de:6443/arcgis/rest/services/SORA/coordinates/GPServer)
'''
class TaskRepositiory:
    # the coordinates extracted and transformed in the Coordinate-System of the Image
    coord = []
    extend = None
    buffer_size = None
    epsg_image = None
    image_path = None
    indicator = None
    time = None


    def __init__(self, input,round):
        self.input = input
        self.round = round

    #image is always in "ETRS_1989_LAEA" needs to transform
    def transformPoint(self,x, y):
        point = arcpy.PointGeometry(arcpy.Point(float(x), float(y)), arcpy.SpatialReference(int(self.epsg_input))).projectAs(
            arcpy.SpatialReference(int(self.epsg_image)))
        return point.centroid

    def getImagePath(self,indicator,time):
        # set  the variables
        self.indicator = indicator
        self.time = time
        # calculate the min extend
        url_spatial_extend = 'https://monitor.ioer.de/backend/sora/GET.php?values={"ind":{"id":"%s"},"format":{"id":"raster"},"query":"getSpatialExtend"}' % (indicator)
        extends_request = requests.get(url_spatial_extend)
        extendJSON = json.loads(extends_request.text)
        extend = extendJSON[0]

        path = os.path.join("/mapsrv_daten/detailviewer/data/{}/Raster {} m/".format(time,extend),"r{}_{}_{}.tif".format(extend,time,indicator))
        absFilePath = os.path.abspath(__file__)[0]
        #local use
        if absFilePath == "C":
            path =r"G:\mapsrv_daten\detailviewer\data\{}\Raster {} m\r{}_{}_{}.tif".format(time,extend,extend,time,indicator)

        self.image_path = path

        # get the epsg of the image
        code = arcpy.Describe(self.image_path).spatialReference
        self.epsg_image = code.PCSCode

    def createPixelValues(self,*args, **kwargs):
        buffer = kwargs.get("buffer",None)
        for x in self.coord:
            pnt = "{} {}".format(x["x"],x["y"])
            res = self.encodePixelValue(arcpy.GetCellValue_management(self.image_path, pnt, "1"))
            # get the buffer average if the paramter is set
            if buffer:
                self.buffer_size = int(buffer)
                buffer_average = self.getBufferAverage(x["x"],x["y"])
                object = {"indicator": self.indicator,
                           "time": self.time,
                           "indicator_value": str(res),
                           "value_buffer":str(buffer_average)
                           }
            else:
                object = {"indicator": self.indicator,
                           "time": self.time,
                           "indicator_value": str(res)}

            x["values"].append(object)

    def extractInput(self):
        # only one time
        if not self.coord:
            json = self.input
            self.epsg_input=json['epsg']
            for c in json['coordinates']:
                id = c['id']
                x = c['x']
                y = c['y']
                x_string = str(x)
                y_string = str(y)
                comma = ','
                x_set = x
                y_set = y

                # remove comma if set
                if comma in x_string:
                    x_set = x_string.replace(",", ".").replace(' ', '').replace('(', '').replace(')', '')

                if comma in y_string:
                    y_set = y_string.replace(",", ".").replace(' ', '').replace('(', '').replace(')', '')

                # transform if needed
                if self.epsg_image != self.epsg_input:
                    pnt_trans = self.transformPoint(x_set,y_set)
                    x_set = pnt_trans.X
                    y_set = pnt_trans.Y

                self.coord.append({'id': id,'x': x_set, 'y': y_set, 'x_org': x, 'y_org': y,"values":[]})

    def getBufferAverage(self,x,y):
        # create the point
        pnt = "{} {}".format(x, y)
        buffer_image = self.image_path.replace("100","1000")
        arcpy.AddMessage(buffer_image)
        return self.encodePixelValue(arcpy.GetCellValue_management(buffer_image, pnt, "1"))


    def encodePixelValue(self,value):
        result = value.getOutput(0).replace(",", ".")
        try:
            set = float(result)
        except ValueError:
            set = 0

        if set <= -100:
            set =0

        return round(set,self.round)

class Result(TaskRepositiory):
    def extractJSON(self):
        result = []
        for x in self.coord:
            result.append({"id":str(x["id"]),"x":str(x["x_org"]),"y":str(x["y_org"]),"values":x["values"]})
        return result

def main():
    # ENV Settings
    arcpy.env.overwriteOutput = 1
    # how to round the values
    round = 2
    # the keys
    indicators = "indicators"
    indicator_id = "id"
    year_id = "year"
    buffer_id = "buffer"
    # user input
    input = json.loads(arcpy.GetParameterAsText(0))
    task = Result(input,round)
    for i in input[indicators]:
        # settings
        indicator = i[indicator_id]
        year = i[year_id]
        if i.has_key("buffer"):
            buffer = int(i[buffer_id])
        else:
            buffer = None
        # create the result
        task.getImagePath(indicator, year)
        task.extractInput()
        task.createPixelValues(buffer=buffer)


    arcpy.SetParameterAsText(1,json.dumps(task.extractJSON()))

if __name__ == '__main__': main()
