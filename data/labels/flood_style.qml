<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 attr="class" type="categorizedSymbol">
    <categories>
      <category value="2" symbol="0" label="2 flood with vegetation (TARGET)" render="true"/>
      <category value="1" symbol="1" label="1 flood open water" render="true"/>
      <category value="3" symbol="2" label="3 permanent water" render="true"/>
      <category value="-1" symbol="3" label="-1 uncertain / cloud" render="true"/>
      <category value="0" symbol="4" label="0 dry" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="fill">
        <layer class="SimpleFill">
          <prop k="color" v="30,95,168,90"/><prop k="outline_color" v="30,95,168,255"/><prop k="outline_width" v="0.5"/>
        </layer>
      </symbol>
      <symbol name="1" type="fill">
        <layer class="SimpleFill">
          <prop k="color" v="10,40,90,90"/><prop k="outline_color" v="10,40,90,255"/><prop k="outline_width" v="0.5"/>
        </layer>
      </symbol>
      <symbol name="2" type="fill">
        <layer class="SimpleFill">
          <prop k="color" v="60,180,200,90"/><prop k="outline_color" v="60,180,200,255"/><prop k="outline_width" v="0.5"/>
        </layer>
      </symbol>
      <symbol name="3" type="fill">
        <layer class="SimpleFill">
          <prop k="color" v="130,130,130,50"/><prop k="outline_color" v="90,90,90,200"/>
          <prop k="outline_style" v="dash"/><prop k="outline_width" v="0.4"/><prop k="style" v="b_diagonal"/>
        </layer>
      </symbol>
      <symbol name="4" type="fill">
        <layer class="SimpleFill">
          <prop k="color" v="200,180,140,40"/><prop k="outline_color" v="160,140,100,200"/><prop k="outline_width" v="0.3"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
